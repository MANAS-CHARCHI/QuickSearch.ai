"""
Async client helper for FastAPI to invoke the AWS SAM Local Lambda Pipeline
(and deployed AWS API Gateway / Lambda endpoints in production).
"""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings


class LambdaPipelineService:
    """Orchestrates calls to the 3 AWS SAM Lambda functions."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 120.0):
        self.base_url = (base_url or settings.SAM_API_URL).rstrip("/")
        self.timeout = timeout

    async def scan_and_extract(
        self,
        *,
        file_id: str,
        user_id: str,
        filename: str,
        mime_type: str,
        category: str = "Other",
        file_bytes: Optional[bytes] = None,
        s3_bucket: Optional[str] = None,
        s3_key: Optional[str] = None,
        invoke_vlm: bool = True,
        invoke_next: bool = False,
    ) -> Dict[str, Any]:
        """Stage 1: Invoke FileScanAndExtractFunction (ClamAV + Text Extraction)."""
        payload: Dict[str, Any] = {
            "file_id": file_id,
            "user_id": user_id,
            "filename": filename,
            "mime_type": mime_type,
            "category": category,
            "invoke_vlm": invoke_vlm,
            "invoke_next": invoke_next,
        }
        if file_bytes is not None:
            payload["file_base64"] = base64.b64encode(file_bytes).decode("ascii")
        if s3_bucket and s3_key:
            payload["s3_bucket"] = s3_bucket
            payload["s3_key"] = s3_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/scan-extract", json=payload)
            return resp.json()

    async def describe_image(
        self,
        *,
        file_id: str,
        filename: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        page_number: int = 1,
    ) -> Dict[str, Any]:
        """Stage 1B: Invoke isolated ImageVLMDescriptionFunction (VLM MicroVM)."""
        payload = {
            "file_id": file_id,
            "filename": filename,
            "mime_type": mime_type,
            "page_number": page_number,
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/describe-image", json=payload)
            return resp.json()

    async def security_scan_and_vectorize(
        self,
        *,
        file_id: str,
        user_id: str,
        filename: str,
        extracted_text: str,
        pages: Optional[List[Dict[str, Any]]] = None,
        category: str = "Other",
        sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Stage 2: Invoke TextSecurityAndVectorizeFunction (SQLi + Prompt Injection ML + pgvector)."""
        payload: Dict[str, Any] = {
            "file_id": file_id,
            "user_id": user_id,
            "filename": filename,
            "extracted_text": extracted_text,
            "pages": pages,
            "category": category,
            "sha256": sha256,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/security-vectorize", json=payload)
            return resp.json()

    async def run_full_pipeline(
        self,
        *,
        file_id: str,
        user_id: str,
        filename: str,
        mime_type: str,
        file_bytes: bytes,
        category: str = "Other",
    ) -> Dict[str, Any]:
        """Run Stage 1 (Virus + Extract + VLM fallback) followed by Stage 2 (ML Security + pgvector)."""
        stage1 = await self.scan_and_extract(
            file_id=file_id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            category=category,
            file_bytes=file_bytes,
            invoke_vlm=True,
            invoke_next=False,
        )
        if stage1.get("status") != "clean":
            return {"stage": "file_scan_extract", "result": stage1}

        stage2 = await self.security_scan_and_vectorize(
            file_id=file_id,
            user_id=user_id,
            filename=filename,
            extracted_text=stage1.get("extracted_text", ""),
            pages=stage1.get("pages"),
            category=category,
            sha256=stage1.get("sha256"),
        )
        return {
            "stage": "completed" if stage2.get("status") == "indexed" else "security_blocked",
            "stage1": stage1,
            "stage2": stage2,
        }


lambda_pipeline_service = LambdaPipelineService()
