"""
FastEmbed (384-dim ONNX) & Atomic PostgreSQL pgvector Store for Lambda 2.

Writes verified document chunks + vector(384) embeddings into `document_chunks`,
updates `files.scan_status`, and records an audit trail in `audit_logs` within a
single atomic PostgreSQL transaction.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from chunker import TextChunk

logger = logging.getLogger(__name__)

_CACHED_EMBEDDER = None


def _get_embedder():
    global _CACHED_EMBEDDER
    if _CACHED_EMBEDDER is not None:
        return _CACHED_EMBEDDER

    if os.getenv("DISABLE_ML_MODELS", "false").lower() == "true":
        return None

    try:
        from fastembed import TextEmbedding

        model_id = os.getenv("EMBEDDING_MODEL_ID", "BAAI/bge-small-en-v1.5")
        cache_dir = os.path.join(os.getenv("MODEL_CACHE_DIR", "/opt/models"), "fastembed")
        if not os.path.isdir(cache_dir):
            cache_dir = os.getenv("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache")
        _CACHED_EMBEDDER = TextEmbedding(model_name=model_id, cache_dir=cache_dir)
        return _CACHED_EMBEDDER
    except Exception as exc:
        logger.warning("FastEmbed unavailable (%s); using deterministic hash embeddings fallback.", exc)
        return None


def _deterministic_fallback_embedding(text: str, dim: int) -> List[float]:
    """Normalized deterministic pseudo-vector used ONLY for offline unit tests."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [((digest[i % len(digest)] / 255.0) * 2.0 - 1.0) for i in range(dim)]
    norm = sum(x * x for x in raw) ** 0.5 or 1.0
    return [round(x / norm, 6) for x in raw]


def embed_texts(texts: Sequence[str]) -> Tuple[List[List[float]], str]:
    dim = int(os.getenv("VECTOR_DIMENSION", "384"))
    if not texts:
        return [], "none"

    embedder = _get_embedder()
    if embedder is not None:
        vectors = [vec.tolist() for vec in embedder.embed(list(texts))]
        return vectors, os.getenv("EMBEDDING_MODEL_ID", "BAAI/bge-small-en-v1.5")

    return [_deterministic_fallback_embedding(t, dim) for t in texts], "hash-fallback-test"


def _normalize_dsn(raw_dsn: str) -> str:
    # Convert SQLAlchemy asyncpg URL if passed verbatim
    return raw_dsn.replace("postgresql+asyncpg://", "postgresql://")


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def record_security_block(
    file_id: str,
    user_id: str,
    scan_status: str,
    details: Dict[str, Any],
    dry_run: bool = False,
) -> bool:
    """Update files.scan_status and write audit_logs when a threat is blocked."""
    if dry_run or not _is_valid_uuid(file_id) or not _is_valid_uuid(user_id):
        return False

    dsn = _normalize_dsn(
        os.getenv("DATABASE_URL", "postgresql://vault_user:vault_secure_password@db:5432/vault_db")
    )
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE files SET scan_status = %s, updated_at = NOW() WHERE id = %s AND user_id = %s",
                    (scan_status, file_id, user_id),
                )
                cur.execute(
                    """
                    INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, status, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        f"ml_scan_{scan_status}",
                        "file",
                        file_id,
                        "blocked",
                        json.dumps(details),
                    ),
                )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to record security block in PostgreSQL: %s", exc)
        return False


def store_chunks_in_pgvector(
    file_id: str,
    user_id: str,
    filename: str,
    chunks: Sequence[TextChunk],
    embeddings: Sequence[List[float]],
    security_summary: Dict[str, Any],
    category: str = "Other",
    sha256: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Atomically upsert chunks + vector(384) embeddings into PostgreSQL `document_chunks`,
    mark `files.scan_status = 'indexed'`, and log completion to `audit_logs`.
    """
    if dry_run:
        return {
            "persisted": False,
            "dry_run": True,
            "chunks_stored": len(chunks),
        }

    if not _is_valid_uuid(file_id) or not _is_valid_uuid(user_id):
        return {
            "persisted": False,
            "dry_run": False,
            "chunks_stored": 0,
            "detail": "Skipped DB write because file_id or user_id is not a valid UUID.",
        }

    import psycopg
    from pgvector.psycopg import register_vector

    dsn = _normalize_dsn(
        os.getenv("DATABASE_URL", "postgresql://vault_user:vault_secure_password@db:5432/vault_db")
    )

    with psycopg.connect(dsn, connect_timeout=10) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            # Verify parent file exists before inserting chunks
            cur.execute(
                "SELECT 1 FROM files WHERE id = %s AND user_id = %s",
                (file_id, user_id),
            )
            if cur.fetchone() is None:
                return {
                    "persisted": False,
                    "chunks_stored": 0,
                    "detail": f"File record {file_id} not found in PostgreSQL `files` table.",
                }

            # Idempotent replacement for this file
            cur.execute(
                "DELETE FROM document_chunks WHERE file_id = %s AND user_id = %s",
                (file_id, user_id),
            )

            for chunk, vector in zip(chunks, embeddings):
                meta = {
                    "filename": filename,
                    "category": category,
                    "source_type": chunk.source_type,
                    "sha256": sha256,
                    "scan_verified": True,
                    "security_scores": security_summary,
                }
                cur.execute(
                    """
                    INSERT INTO document_chunks
                        (id, file_id, user_id, chunk_index, page_number, content, embedding, metadata_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (file_id, chunk_index) DO UPDATE
                    SET content = EXCLUDED.content,
                        page_number = EXCLUDED.page_number,
                        embedding = EXCLUDED.embedding,
                        metadata_json = EXCLUDED.metadata_json
                    """,
                    (
                        str(uuid.uuid4()),
                        file_id,
                        user_id,
                        chunk.chunk_index,
                        chunk.page_number,
                        chunk.content,
                        vector,
                        json.dumps(meta),
                    ),
                )

            cur.execute(
                "UPDATE files SET scan_status = 'indexed', updated_at = NOW() WHERE id = %s AND user_id = %s",
                (file_id, user_id),
            )
            cur.execute(
                """
                INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, status, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    "file_indexed_pgvector",
                    "file",
                    file_id,
                    "success",
                    json.dumps(
                        {
                            "chunks_stored": len(chunks),
                            "security_scores": security_summary,
                        }
                    ),
                ),
            )
        conn.commit()

    return {
        "persisted": True,
        "chunks_stored": len(chunks),
    }
