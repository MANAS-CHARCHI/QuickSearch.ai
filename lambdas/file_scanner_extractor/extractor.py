"""
Multi-Format Text Extractor & Sparse-Page Image Rasterizer for Lambda 1.

Supports:
- PDF (via PyMuPDF / fitz) with per-page text extraction + automatic 150 DPI PNG
  rasterization for scanned / unreadable pages that need VLM visual understanding.
- DOCX (via python-docx) including paragraphs and tables.
- Plain text formats (TXT, MD, CSV, JSON, XML, LOG).
- Images (PNG, JPG, JPEG, WEBP) routed directly to Lambda 3 (VLM MicroVM).
"""
from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
IMAGE_MIME_PREFIXES = ("image/",)
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".log", ".yaml", ".yml"}


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    needs_vlm: bool = False
    image_base64: Optional[str] = None
    mime_type: Optional[str] = None


@dataclass
class ExtractionResult:
    extracted_text: str
    pages: List[ExtractedPage] = field(default_factory=list)
    needs_vlm: bool = False
    vlm_pages: List[Dict] = field(default_factory=list)
    extractor_used: str = "text"


def _get_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename.lower().strip())
    return ext


def _is_sparse_text(text: str, min_chars: int) -> bool:
    meaningful = "".join(ch for ch in text if not ch.isspace())
    return len(meaningful) < min_chars


def extract_content(
    data: bytes,
    filename: str,
    mime_type: Optional[str] = None,
    sparse_min_chars: Optional[int] = None,
) -> ExtractionResult:
    """
    Extract text from supported document formats, and flag images or unreadable/scanned
    PDF pages for routing to the isolated VLM MicroVM Lambda.
    """
    ext = _get_extension(filename)
    mime = (mime_type or "").lower().strip()
    min_chars = (
        sparse_min_chars
        if sparse_min_chars is not None
        else int(os.getenv("SPARSE_TEXT_MIN_CHARS", "50"))
    )

    # 1. Direct Image Upload -> Route to Lambda 3 (VLM MicroVM)
    if ext in IMAGE_EXTENSIONS or any(mime.startswith(p) for p in IMAGE_MIME_PREFIXES):
        encoded = base64.b64encode(data).decode("ascii")
        resolved_mime = mime if mime.startswith("image/") else f"image/{ext.lstrip('.') or 'png'}"
        page = ExtractedPage(
            page_number=1,
            text="",
            needs_vlm=True,
            image_base64=encoded,
            mime_type=resolved_mime,
        )
        return ExtractionResult(
            extracted_text="",
            pages=[page],
            needs_vlm=True,
            vlm_pages=[
                {
                    "page_number": 1,
                    "mime_type": resolved_mime,
                    "image_base64": encoded,
                }
            ],
            extractor_used="image-vlm-route",
        )

    # 2. PDF Document (PyMuPDF)
    if ext == ".pdf" or mime == "application/pdf":
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        pages: List[ExtractedPage] = []
        vlm_pages: List[Dict] = []
        all_texts: List[str] = []

        try:
            for idx, pdf_page in enumerate(doc, start=1):
                page_text = (pdf_page.get_text("text") or "").strip()
                sparse = _is_sparse_text(page_text, min_chars)
                img_b64 = None

                if sparse:
                    # Rasterize scanned/unreadable page to 150 DPI PNG for VLM MicroVM
                    pix = pdf_page.get_pixmap(dpi=150)
                    img_b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
                    vlm_pages.append(
                        {
                            "page_number": idx,
                            "mime_type": "image/png",
                            "image_base64": img_b64,
                        }
                    )

                pages.append(
                    ExtractedPage(
                        page_number=idx,
                        text=page_text,
                        needs_vlm=sparse,
                        image_base64=img_b64,
                        mime_type="image/png" if sparse else None,
                    )
                )
                if page_text:
                    all_texts.append(page_text)
        finally:
            doc.close()

        return ExtractionResult(
            extracted_text="\n\n".join(all_texts).strip(),
            pages=pages,
            needs_vlm=len(vlm_pages) > 0,
            vlm_pages=vlm_pages,
            extractor_used="pymupdf",
        )

    # 3. DOCX Document (python-docx)
    if (
        ext == ".docx"
        or mime
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        from docx import Document

        document = Document(io.BytesIO(data))
        parts: List[str] = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))

        full_text = "\n".join(parts).strip()
        return ExtractionResult(
            extracted_text=full_text,
            pages=[ExtractedPage(page_number=1, text=full_text, needs_vlm=False)],
            needs_vlm=False,
            extractor_used="python-docx",
        )

    # 4. Plain Text / Structured Text (TXT, MD, CSV, JSON, etc.)
    if ext in TEXT_EXTENSIONS or mime.startswith("text/") or mime == "application/json":
        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            decoded = data.decode("latin-1", errors="replace")

        full_text = decoded.strip()
        return ExtractionResult(
            extracted_text=full_text,
            pages=[ExtractedPage(page_number=1, text=full_text, needs_vlm=False)],
            needs_vlm=False,
            extractor_used="utf8-text",
        )

    # 5. Best-effort UTF-8 fallback for unknown text-like payloads
    decoded = data.decode("utf-8", errors="replace").strip()
    return ExtractionResult(
        extracted_text=decoded,
        pages=[ExtractedPage(page_number=1, text=decoded, needs_vlm=False)],
        needs_vlm=False,
        extractor_used="fallback-utf8",
    )
