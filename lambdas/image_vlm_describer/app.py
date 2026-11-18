"""
Lambda 3 Handler: ImageVLMDescriptionFunction (Isolated VLM MicroVM)

Security Boundary:
- Holds ZERO database credentials, ZERO Redis access, and ZERO S3 write permissions.
- Receives a single untrusted image (base64), sanitizes it against image-parser exploits,
  runs a lightweight Vision-Language Model (SmolVLM-500M-Instruct or local Ollama),
  and returns a rich semantic description + visible text transcription.
- Downstream text MUST still pass through Lambda 2's SQLi + Prompt Injection ML scanners
  to neutralize visual prompt injection attacks hidden inside images.
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Tuple

from vlm_engine import describe_image

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

    file_id = str(payload.get("file_id", "local-image"))
    filename = str(payload.get("filename", "image.png"))
    page_number = int(payload.get("page_number", 1))
    image_b64 = payload.get("image_base64")
    vlm_mode = payload.get("vlm_mode")  # Optional override (embedded | ollama | mock)

    if not image_b64:
        return _format_response(
            {"status": "error", "file_id": file_id, "detail": "Missing 'image_base64' field."},
            is_api_gw,
            status_code=400,
        )

    try:
        image_bytes = base64.b64decode(image_b64)
        result = describe_image(image_bytes, vlm_mode=vlm_mode)
    except Exception as exc:
        logger.exception("VLM image processing failed for file_id=%s", file_id)
        return _format_response(
            {"status": "error", "file_id": file_id, "detail": f"Image processing failed: {exc}"},
            is_api_gw,
            status_code=422,
        )

    return _format_response(
        {
            "status": "described",
            "file_id": file_id,
            "filename": filename,
            "page_number": page_number,
            "visual_description": result.visual_description,
            "visible_text": result.visible_text,
            "combined_text": result.combined_text,
            "document_category_hint": result.document_category_hint,
            "model_used": result.model_used,
            "image_metadata": {
                "width": result.image_width,
                "height": result.image_height,
                "format": result.image_format,
            },
        },
        is_api_gw,
        status_code=200,
    )
