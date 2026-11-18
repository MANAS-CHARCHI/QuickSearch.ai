"""
Lambda 1 Handler: FileScanAndExtractFunction

Pipeline Stage 1:
1. Fetch file bytes (from S3/MinIO or direct base64 payload).
2. Scan file bytes for viruses/malware using ClamAV (clamav:3310 INSTREAM).
3. If infected -> reject immediately and stop pipeline.
4. Extract text (PDF / DOCX / TXT).
5. If image or sparse/unreadable PDF page -> invoke Lambda 3 (Isolated VLM MicroVM).
6. Return extracted text (+ optionally chain directly into Lambda 2 for ML security scan & pgvector storage).
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from extractor import extract_content
from scanner import scan_bytes_with_clamav

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _parse_event(event: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Support both direct Lambda invocation and API Gateway proxy events."""
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


def _load_file_bytes(payload: Dict[str, Any]) -> bytes:
    """Load file bytes from direct base64 payload or S3/MinIO bucket."""
    if payload.get("file_base64"):
        return base64.b64decode(payload["file_base64"])

    s3_bucket = payload.get("s3_bucket")
    s3_key = payload.get("s3_key")
    if s3_bucket and s3_key:
        import boto3

        endpoint_url = os.getenv("S3_ENDPOINT_URL") or None
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        return obj["Body"].read()

    raise ValueError("Event must include either 'file_base64' or both 's3_bucket' and 's3_key'.")


def _get_lambda_client():
    import boto3

    endpoint_url = os.getenv("LAMBDA_ENDPOINT_URL") or None
    return boto3.client(
        "lambda",
        endpoint_url=endpoint_url,
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )


def _invoke_vlm_microvm(
    file_id: str,
    filename: str,
    vlm_page: Dict[str, Any],
) -> Dict[str, Any]:
    """Invoke isolated Lambda 3 (ImageVLMDescriptionFunction) to describe an image/scan."""
    fn_name = os.getenv("VLM_FUNCTION_NAME", "ImageVLMDescriptionFunction")
    client = _get_lambda_client()
    vlm_event = {
        "file_id": file_id,
        "filename": filename,
        "page_number": vlm_page["page_number"],
        "mime_type": vlm_page.get("mime_type", "image/png"),
        "image_base64": vlm_page["image_base64"],
    }
    resp = client.invoke(
        FunctionName=fn_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(vlm_event).encode("utf-8"),
    )
    raw = resp["Payload"].read().decode("utf-8")
    return json.loads(raw)


def _invoke_security_vectorizer(next_payload: Dict[str, Any], async_invoke: bool = False) -> Dict[str, Any]:
    """Forward extracted text to Lambda 2 (TextSecurityAndVectorizeFunction)."""
    fn_name = os.getenv("SECURITY_VECTOR_FUNCTION_NAME", "TextSecurityAndVectorizeFunction")
    client = _get_lambda_client()
    invocation_type = "Event" if async_invoke else "RequestResponse"
    resp = client.invoke(
        FunctionName=fn_name,
        InvocationType=invocation_type,
        Payload=json.dumps(next_payload).encode("utf-8"),
    )
    if async_invoke:
        return {"invoked_async": True, "status_code": resp.get("StatusCode", 202)}
    raw = resp["Payload"].read().decode("utf-8")
    return json.loads(raw)


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    payload, is_api_gw = _parse_event(event)

    file_id = str(payload.get("file_id", "local-test-file"))
    user_id = str(payload.get("user_id", "local-test-user"))
    filename = str(payload.get("filename", "document.txt"))
    mime_type = payload.get("mime_type")
    category = str(payload.get("category", "Other"))
    invoke_vlm = bool(payload.get("invoke_vlm", False))
    invoke_next = bool(payload.get("invoke_next", False))
    async_next = bool(payload.get("async_next", False))

    try:
        file_bytes = _load_file_bytes(payload)
    except Exception as exc:
        logger.exception("Failed to load file bytes for file_id=%s", file_id)
        return _format_response(
            {"status": "error", "file_id": file_id, "detail": str(exc)},
            is_api_gw,
            status_code=400,
        )

    # 1. Virus & Malware Scan (ClamAV INSTREAM + EICAR signature guard)
    scan_result = scan_bytes_with_clamav(file_bytes)
    if not scan_result.is_clean:
        logger.warning(
            "File rejected by antivirus: file_id=%s status=%s threat=%s",
            file_id,
            scan_result.status,
            scan_result.threat_name,
        )
        return _format_response(
            {
                "status": scan_result.status,
                "file_id": file_id,
                "user_id": user_id,
                "filename": filename,
                "sha256": scan_result.sha256,
                "file_size": scan_result.file_size,
                "threat_name": scan_result.threat_name,
                "scanner_engine": scan_result.scanner_engine,
                "detail": scan_result.detail,
                "forwarded": False,
            },
            is_api_gw,
            status_code=422 if scan_result.status == "infected" else 500,
        )

    # 2. Multi-Format Text Extraction
    try:
        extraction = extract_content(file_bytes, filename=filename, mime_type=mime_type)
    except Exception as exc:
        logger.exception("Text extraction failed for file_id=%s", file_id)
        return _format_response(
            {
                "status": "extraction_error",
                "file_id": file_id,
                "detail": str(exc),
            },
            is_api_gw,
            status_code=500,
        )

    pages_out: List[Dict[str, Any]] = []
    vlm_descriptions: List[Dict[str, Any]] = []

    # 3. Optional VLM MicroVM routing for images or unreadable/scanned PDF pages
    for page in extraction.pages:
        page_text = page.text
        source_type = "text"

        if page.needs_vlm and invoke_vlm and page.image_base64:
            try:
                vlm_res = _invoke_vlm_microvm(
                    file_id=file_id,
                    filename=filename,
                    vlm_page={
                        "page_number": page.page_number,
                        "mime_type": page.mime_type or "image/png",
                        "image_base64": page.image_base64,
                    },
                )
                combined_vlm = vlm_res.get("combined_text") or vlm_res.get("visual_description") or ""
                if combined_vlm:
                    page_text = f"{page_text}\n\n{combined_vlm}".strip() if page_text else combined_vlm
                    source_type = "vlm_description"
                    vlm_descriptions.append(vlm_res)
            except Exception as exc:
                logger.warning("VLM MicroVM invocation failed on page %d: %s", page.page_number, exc)

        pages_out.append(
            {
                "page_number": page.page_number,
                "text": page_text,
                "needs_vlm": page.needs_vlm,
                "source_type": source_type,
            }
        )

    merged_text = "\n\n".join(p["text"] for p in pages_out if p["text"]).strip()

    result_payload: Dict[str, Any] = {
        "status": "clean",
        "file_id": file_id,
        "user_id": user_id,
        "filename": filename,
        "category": category,
        "sha256": scan_result.sha256,
        "file_size": scan_result.file_size,
        "scanner_engine": scan_result.scanner_engine,
        "extractor_used": extraction.extractor_used,
        "needs_vlm": extraction.needs_vlm,
        "vlm_processed": len(vlm_descriptions) > 0,
        "char_count": len(merged_text),
        "extracted_text": merged_text,
        "pages": pages_out,
        "forwarded": False,
    }

    # Include rasterized page references only when VLM wasn't invoked inline
    if extraction.needs_vlm and not invoke_vlm:
        result_payload["vlm_pending_pages"] = len(extraction.vlm_pages)

    # 4. Optional Direct Chaining into Lambda 2 (ML Security + pgvector)
    if invoke_next and merged_text:
        next_event = {
            "file_id": file_id,
            "user_id": user_id,
            "filename": filename,
            "category": category,
            "sha256": scan_result.sha256,
            "extracted_text": merged_text,
            "pages": pages_out,
        }
        try:
            next_res = _invoke_security_vectorizer(next_event, async_invoke=async_next)
            result_payload["forwarded"] = True
            result_payload["stage2_result"] = next_res
        except Exception as exc:
            logger.exception("Failed forwarding file_id=%s to Lambda 2", file_id)
            result_payload["forward_error"] = str(exc)

    return _format_response(result_payload, is_api_gw, status_code=200)
