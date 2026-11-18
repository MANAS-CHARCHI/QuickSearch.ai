"""
Lambda 2 Handler: TextSecurityAndVectorizeFunction

Pipeline Stage 2:
1. Normalize text (Unicode NFKC, invisible zero-width character detection, base64 snippet extraction).
2. Run ML Model 1 (SQL Injection ONNX classifier) over overlapping sliding windows.
3. Run ML Model 2 (AI Prompt Injection / Manipulator ONNX classifier) over overlapping sliding windows.
4. Security Gate:
   - If SQLi or Prompt Injection exceeds threshold -> block immediately, update PostgreSQL
     `files.scan_status` & `audit_logs`, and write ZERO chunks to pgvector.
5. Chunk verified text recursively preserving page & VLM source metadata.
6. Generate 384-dim embeddings (FastEmbed `BAAI/bge-small-en-v1.5`) and atomically upsert
   into PostgreSQL `document_chunks` (`pgvector` HNSW cosine index).
"""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import asdict
from typing import Any, Dict, Tuple

from chunker import chunk_document
from pgvector_store import embed_texts, record_security_block, store_chunks_in_pgvector
from scanners import normalize_and_inspect, scan_prompt_injection, scan_sql_injection

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _parse_event(event: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    if "body" in event and isinstance(event.get("body"), str):
        body_str = event["body"]
        if event.get("isBase64Encoded"):
            body_str = base64.b64decode(body_str).decode("utf-8")
        return json.loads(body_str or "{}"), True
    return event, False


def _format_response(payload: Dict[str, Any], is_api_gw: bool, status_code: int = 200) -> Dict[str, Any]:
    if not is_api_gw:
        return payload
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    payload, is_api_gw = _parse_event(event)

    file_id = str(payload.get("file_id", "local-test-file"))
    user_id = str(payload.get("user_id", "local-test-user"))
    filename = str(payload.get("filename", "document.txt"))
    category = str(payload.get("category", "Other"))
    sha256 = payload.get("sha256")
    pages = payload.get("pages")
    extracted_text = str(payload.get("extracted_text") or "")
    dry_run = bool(payload.get("dry_run", False))

    if not extracted_text.strip() and pages:
        extracted_text = "\n\n".join(
            str(p.get("text") or "").strip() for p in pages if p.get("text")
        ).strip()

    if not extracted_text.strip():
        return _format_response(
            {
                "status": "error",
                "file_id": file_id,
                "detail": "No extracted text provided for security scanning and vectorization.",
            },
            is_api_gw,
            status_code=400,
        )

    # 1. Text Normalization & Obfuscation Inspection
    norm = normalize_and_inspect(extracted_text)

    # 2. ML Security Scan 1: SQL Injection
    sqli_report = scan_sql_injection(
        norm.normalized_text,
        extra_snippets=norm.decoded_base64_snippets,
    )

    # 3. ML Security Scan 2: AI Prompt Injection / Manipulator Text
    pi_report = scan_prompt_injection(
        norm.normalized_text,
        extra_snippets=norm.decoded_base64_snippets,
        obfuscation_flagged=norm.obfuscation_flagged,
    )

    security_summary = {
        "sqli_score": sqli_report.max_score,
        "sqli_engine": sqli_report.engine,
        "prompt_injection_score": pi_report.max_score,
        "prompt_injection_engine": pi_report.engine,
        "invisible_chars_stripped": norm.invisible_char_count,
        "obfuscation_flagged": norm.obfuscation_flagged,
    }

    # 4. Security Gate — Reject & Quarantine before any chunking or VectorDB writes
    if sqli_report.is_blocked or pi_report.is_blocked:
        if sqli_report.is_blocked and pi_report.is_blocked:
            block_status = "blocked_sqli_and_prompt_injection"
        elif sqli_report.is_blocked:
            block_status = "blocked_sqli"
        else:
            block_status = "blocked_prompt_injection"

        logger.warning(
            "Security gate blocked file_id=%s status=%s sqli=%.3f pi=%.3f",
            file_id,
            block_status,
            sqli_report.max_score,
            pi_report.max_score,
        )

        record_security_block(
            file_id=file_id,
            user_id=user_id,
            scan_status=block_status,
            details={
                "sqli": asdict(sqli_report),
                "prompt_injection": asdict(pi_report),
            },
            dry_run=dry_run,
        )

        return _format_response(
            {
                "status": block_status,
                "file_id": file_id,
                "user_id": user_id,
                "filename": filename,
                "chunks_stored": 0,
                "security_summary": security_summary,
                "sqli_report": asdict(sqli_report),
                "prompt_injection_report": asdict(pi_report),
            },
            is_api_gw,
            status_code=422,
        )

    # 5. Chunk Verified Text
    normalized_pages = None
    if pages:
        normalized_pages = [
            {
                "page_number": int(p.get("page_number", 1)),
                "source_type": str(p.get("source_type", "text")),
                "text": normalize_and_inspect(str(p.get("text") or "")).normalized_text,
            }
            for p in pages
        ]

    chunks = chunk_document(norm.normalized_text, pages=normalized_pages)
    embeddings, embed_model = embed_texts([c.content for c in chunks])

    # 6. Atomic PostgreSQL pgvector Upsert
    try:
        storage_result = store_chunks_in_pgvector(
            file_id=file_id,
            user_id=user_id,
            filename=filename,
            chunks=chunks,
            embeddings=embeddings,
            security_summary=security_summary,
            category=category,
            sha256=sha256,
            dry_run=dry_run,
        )
    except Exception as exc:
        logger.exception("PostgreSQL pgvector upsert failed for file_id=%s", file_id)
        return _format_response(
            {
                "status": "storage_error",
                "file_id": file_id,
                "detail": str(exc),
                "security_summary": security_summary,
            },
            is_api_gw,
            status_code=500,
        )

    return _format_response(
        {
            "status": "indexed",
            "file_id": file_id,
            "user_id": user_id,
            "filename": filename,
            "chunks_created": len(chunks),
            "embedding_model": embed_model,
            "vector_dimension": len(embeddings[0]) if embeddings else 0,
            "storage": storage_result,
            "security_summary": security_summary,
        },
        is_api_gw,
        status_code=200,
    )
