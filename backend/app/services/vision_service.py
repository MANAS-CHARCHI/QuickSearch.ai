"""
Lightweight VLM Image Description & Document Summarization Engine (Zero Tesseract / Zero Heavy OCR).

Image Short Description Priority:
1. Gemini Vision API (`GEMINI_API_KEY` in .env) — fast 1-2 sentence short description + visible text.
2. Local Ollama VLM (`OLLAMA_URL` in .env, e.g. moondream / llava / qwen2.5vl).
3. AWS SAM Lambda 3 VLM (`SAM_API_URL/describe-image`, SmolVLM-500M-Instruct) if running locally.
4. Lightweight Pillow metadata fallback (resolution, orientation, tone, EXIF) when no VLM is configured.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import io
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image, ImageOps, ImageStat

from app.core.config import settings

logger = logging.getLogger("vaultcity.vision")

Image.MAX_IMAGE_PIXELS = 25_000_000

VISION_JSON_PROMPT = (
    "Analyze this image for a personal document vault. "
    "Return ONLY valid JSON (no markdown fences) with these exact keys:\n"
    '- "summary": 1-2 crisp sentences giving a short description of what this image is about (subject, document type, key visible info).\n'
    '- "visible_text": any readable printed/handwritten text visible in the image (empty string if none).\n'
    '- "document_type": short label such as "Identity Card", "Invoice / Receipt", "Medical Report", "Resume", "Screenshot", "Diagram", "Photograph", or "Scanned Document".\n'
    '- "category_hint": one of "Identity", "Financial", "Medical", "Personal", "Other".'
)


@dataclass
class VisionResult:
    summary: str
    visible_text: str
    combined_text: str
    document_type: str
    category_hint: Optional[str]
    engine: str
    width: int
    height: int
    image_format: str


def _sanitize_image_to_jpeg(
    image_bytes: bytes, max_dim: int = 1024
) -> Tuple[Image.Image, bytes, str, Tuple[int, int], Dict[str, Any]]:
    """Decode safely, capture basic EXIF info, strip EXIF into clean RGB image + JPEG bytes."""
    with Image.open(io.BytesIO(image_bytes)) as raw_img:
        orig_format = (raw_img.format or "IMAGE").upper()
        exif_meta: Dict[str, Any] = {}
        try:
            exif = raw_img.getexif()
            if exif:
                if 272 in exif:
                    exif_meta["camera"] = str(exif[272]).strip()
                if 306 in exif:
                    exif_meta["captured_at"] = str(exif[306]).strip()
        except Exception:
            pass

        transposed = ImageOps.exif_transpose(raw_img)
        rgb = transposed.convert("RGB") if transposed.mode != "RGB" else transposed.copy()
        orig_size = (rgb.width, rgb.height)

    work = rgb.copy()
    if max(work.width, work.height) > max_dim:
        work.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    clean = Image.new("RGB", work.size)
    clean.paste(work)
    buf = io.BytesIO()
    clean.save(buf, format="JPEG", quality=85)
    return clean, buf.getvalue(), orig_format, orig_size, exif_meta


def _extract_json_block(raw_text: str) -> Optional[Dict[str, Any]]:
    text = (raw_text or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return None
    return None


async def _try_gemini_vision(jpeg_bytes: bytes) -> Optional[Dict[str, Any]]:
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key:
        return None
    model = settings.GEMINI_VISION_MODEL or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": VISION_JSON_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64.b64encode(jpeg_bytes).decode("ascii"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, params={"key": api_key}, json=payload)
            resp.raise_for_status()
            data = resp.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        parsed = _extract_json_block(text)
        if parsed and (parsed.get("summary") or parsed.get("visible_text")):
            parsed["_engine"] = f"vlm:gemini:{model}"
            return parsed
    except Exception as exc:
        logger.warning("Gemini VLM call failed (%s); trying next VLM tier.", exc)
    return None


async def _try_ollama_vision(jpeg_bytes: bytes) -> Optional[Dict[str, Any]]:
    ollama_url = (settings.OLLAMA_URL or "").strip().rstrip("/")
    if not ollama_url:
        return None
    model = settings.OLLAMA_VISION_MODEL or "llava"
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": VISION_JSON_PROMPT,
                    "images": [base64.b64encode(jpeg_bytes).decode("ascii")],
                    "stream": False,
                    "format": "json",
                },
            )
            resp.raise_for_status()
            text = resp.json().get("response", "")
        parsed = _extract_json_block(text)
        if parsed and (parsed.get("summary") or parsed.get("visible_text")):
            parsed["_engine"] = f"vlm:ollama:{model}"
            return parsed
    except Exception as exc:
        logger.warning("Ollama VLM call failed (%s); trying next VLM tier.", exc)
    return None


async def _try_sam_lambda_vlm(jpeg_bytes: bytes, filename: str) -> Optional[Dict[str, Any]]:
    if not settings.USE_SAM_PIPELINE:
        return None
    sam_url = (settings.SAM_API_URL or "").strip().rstrip("/")
    if not sam_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{sam_url}/describe-image",
                json={
                    "filename": filename,
                    "image_base64": base64.b64encode(jpeg_bytes).decode("ascii"),
                },
            )
            resp.raise_for_status()
            data = resp.json()
        summary = str(data.get("visual_description") or data.get("summary") or "").strip()
        visible_text = str(data.get("visible_text") or "").strip()
        if summary or visible_text:
            return {
                "summary": summary,
                "visible_text": visible_text,
                "document_type": data.get("document_category_hint") or "Image",
                "category_hint": data.get("document_category_hint"),
                "_engine": f"vlm:sam:{data.get('model_used', 'smolvlm')}",
            }
    except Exception:
        return None
    return None


def _pillow_metadata_fallback(
    img: Image.Image,
    orig_format: str,
    orig_size: Tuple[int, int],
    exif_meta: Dict[str, Any],
    filename: str,
) -> Tuple[str, str, Optional[str]]:
    """Fast zero-model Pillow fallback when no VLM provider is configured yet."""
    w, h = orig_size
    orientation = "landscape" if w > h * 1.15 else ("portrait" if h > w * 1.15 else "square")
    stat = ImageStat.Stat(img)
    brightness = sum(stat.mean[:3]) / 3.0
    tone = (
        "light-background document/page"
        if brightness > 205
        else ("dark-themed screen/photo" if brightness < 70 else "full-color visual")
    )

    lower = filename.lower()
    doc_type = f"{orig_format} Image"
    category_hint: Optional[str] = None
    if any(k in lower for k in ("aadhaar", "passport", "pan", "license", "id_card", "idcard")):
        doc_type = "Identity Image"
        category_hint = "Identity"
    elif any(k in lower for k in ("invoice", "receipt", "bill", "tax", "bank")):
        doc_type = "Financial Image"
        category_hint = "Financial"
    elif any(k in lower for k in ("medical", "lab", "prescription", "xray", "report")):
        doc_type = "Medical Image"
        category_hint = "Medical"

    extras = []
    if exif_meta.get("camera"):
        extras.append(f"camera: {exif_meta['camera']}")
    if exif_meta.get("captured_at"):
        extras.append(f"captured: {exif_meta['captured_at']}")
    extra_str = f" ({', '.join(extras)})" if extras else ""

    summary = (
        f"{doc_type}: {orientation} {orig_format} ({w}x{h}px), {tone}{extra_str}. "
        f"Set GEMINI_API_KEY or OLLAMA_URL in backend/.env to enable VLM visual summaries."
    )
    return summary, doc_type, category_hint


async def analyze_image(image_bytes: bytes, filename: str) -> VisionResult:
    """Run Tier 1 (Gemini VLM) -> Tier 2 (Ollama VLM) -> Tier 3 (SAM VLM) -> Pillow metadata fallback."""
    clean_img, jpeg_bytes, orig_format, orig_size, exif_meta = await asyncio.to_thread(
        _sanitize_image_to_jpeg, image_bytes
    )
    w, h = orig_size

    vlm_data = await _try_gemini_vision(jpeg_bytes)
    if vlm_data is None:
        vlm_data = await _try_ollama_vision(jpeg_bytes)
    if vlm_data is None:
        vlm_data = await _try_sam_lambda_vlm(jpeg_bytes, filename)

    if vlm_data is not None:
        summary = str(vlm_data.get("summary") or "").strip()
        visible_text = str(vlm_data.get("visible_text") or "").strip()
        doc_type = str(vlm_data.get("document_type") or f"{orig_format} Image").strip()
        category_hint = vlm_data.get("category_hint")
        engine = str(vlm_data.get("_engine") or "vlm")
        combined = f"[Image Summary]\n{summary}\n\n[Visible Text]\n{visible_text}".strip() if visible_text else summary
        return VisionResult(
            summary=summary or f"{doc_type} ({w}x{h}px {orig_format})",
            visible_text=visible_text,
            combined_text=combined,
            document_type=doc_type,
            category_hint=category_hint if category_hint in {"Identity", "Financial", "Medical", "Personal", "Other"} else None,
            engine=engine,
            width=w,
            height=h,
            image_format=orig_format,
        )

    summary, doc_type, category_hint = _pillow_metadata_fallback(
        clean_img, orig_format, orig_size, exif_meta, filename
    )
    return VisionResult(
        summary=summary,
        visible_text="",
        combined_text=summary,
        document_type=doc_type,
        category_hint=category_hint,
        engine="pillow-metadata-fallback",
        width=w,
        height=h,
        image_format=orig_format,
    )


def summarize_text_document(text: str, filename: str, doc_type: str, page_count: int) -> str:
    """Create a crisp short description from extracted pypdf / DOCX / text content."""
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    if not clean:
        return f"{doc_type} ({filename}, {page_count} page{'s' if page_count != 1 else ''}) verified and stored securely."

    sentences = re.split(r"(?<=[.!?])\s+", clean)
    picked: List[str] = []
    total_len = 0
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if total_len + len(s) > 280 and picked:
            break
        picked.append(s)
        total_len += len(s) + 1
        if len(picked) >= 2 or total_len >= 220:
            break

    snippet = " ".join(picked) if picked else clean[:260]
    if len(snippet) > 300:
        snippet = snippet[:297].rsplit(" ", 1)[0] + "..."
    elif len(clean) > len(snippet) + 20 and not snippet.endswith((".", "!", "?", "...")):
        snippet += "..."

    word_count = len(re.findall(r"\w+", clean))
    return f"{doc_type} (~{word_count} words): {snippet}"
