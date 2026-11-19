"""
Tesseract OCR (English-Only, High-Accuracy tessdata_best) & VLM Image Description Engine.

Features:
1. Pure English-only Tesseract OCR (`-l eng --oem 1`) with high-accuracy traineddata.
2. Intelligent image preprocessing for maximum OCR fidelity:
   - EXIF orientation correction
   - Dynamic scaling for small document photos/receipts
   - Grayscale and autocontrast enhancement
   - Adaptive PSM fallback (PSM 3 full-page auto segmentation -> PSM 6 uniform text block)
3. Multi-tier visual summary:
   - Tier 1: Gemini Vision / Ollama / SAM VLM (when configured in .env)
   - Tier 2: OCR keyword and document structure summarizer (always available locally)
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image, ImageOps, ImageStat

from app.core.config import settings
from app.services.claude_tracker import call_claude_messages

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
    image_bytes: bytes, max_dim: int = 1600
) -> Tuple[Image.Image, bytes, str, Tuple[int, int], Dict[str, Any]]:
    """Decode safely, capture EXIF info, strip EXIF into clean RGB image + JPEG bytes."""
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
    clean.save(buf, format="JPEG", quality=88)
    return clean, buf.getvalue(), orig_format, orig_size, exif_meta


def _preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """Prepare image for optimal English Tesseract OCR recognition."""
    # Convert to grayscale
    gray = ImageOps.grayscale(img)

    # Dynamic scale: Tesseract accuracy peaks when uppercase characters are ~30-40 pixels tall
    # For small photos or receipts under 1400px wide, upscale with Lanczos
    w, h = gray.size
    if max(w, h) < 1400:
        scale = min(2.5, 1600.0 / max(1, max(w, h)))
        if scale > 1.1:
            gray = gray.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    # Enhance contrast to make faint ink and scans crisp
    enhanced = ImageOps.autocontrast(gray, cutoff=0.5)
    return enhanced


def _run_tesseract_english_sync(img: Image.Image) -> str:
    """Run Tesseract OCR strictly with English neural-net LSTM model (--oem 1 -l eng)."""
    try:
        import pytesseract
    except ImportError:
        logger.warning("pytesseract is not installed; skipping OCR.")
        return ""

    try:
        prep = _preprocess_for_ocr(img)

        # Primary pass: PSM 3 (Fully automatic page segmentation)
        config_psm3 = "--oem 1 -l eng --psm 3"
        raw_psm3 = pytesseract.image_to_string(prep, config=config_psm3) or ""
        clean_psm3 = _clean_ocr_text(raw_psm3)

        # Secondary pass if text is sparse or table-like (PSM 6: Assume a single uniform block of text)
        words_psm3 = len(re.findall(r"[A-Za-z0-9]{2,}", clean_psm3))
        if words_psm3 < 15:
            config_psm6 = "--oem 1 -l eng --psm 6"
            raw_psm6 = pytesseract.image_to_string(prep, config=config_psm6) or ""
            clean_psm6 = _clean_ocr_text(raw_psm6)
            words_psm6 = len(re.findall(r"[A-Za-z0-9]{2,}", clean_psm6))
            if words_psm6 > words_psm3:
                return clean_psm6

        return clean_psm3
    except Exception as exc:
        logger.warning("Tesseract English OCR error: %s", exc)
        return ""


def _clean_ocr_text(text: str) -> str:
    """Normalize OCR text whitespace while preserving lines and paragraphs."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in (text or "").splitlines()]
    clean_lines = [ln for ln in lines if any(ch.isalnum() for ch in ln) or len(ln) >= 2]
    return "\n".join(clean_lines).strip()


def _infer_document_type_and_category(
    ocr_text: str, filename: str
) -> Tuple[str, Optional[str]]:
    """Classify document type and category from extracted English text."""
    lower = f"{filename} {ocr_text}".lower()

    if any(k in lower for k in ("mutual fund", "portfolio", "holdings", "equity related", "net asset", "flexi cap", "shares", "stocks", "nifty", "sensex")):
        return "Mutual Fund Portfolio / Holdings Report", "Financial"
    if any(k in lower for k in ("aadhaar", "passport", "driving licen", "driver license", "pan card", "permanent account", "republic of india", "identity card", "national id", "voter id")):
        return "Identity Document", "Identity"
    if any(k in lower for k in ("invoice", "receipt", "total amount", "tax invoice", "subtotal", "gst", "amount due", "bank statement", "account number", "transaction id", "payment receipt", "bill to")):
        return "Financial Document / Receipt", "Financial"
    if any(k in lower for k in ("patient", "diagnosis", "prescription", "hospital", "clinic", "blood pressure", "lab report", "dr.", "doctor", "medical")):
        return "Medical Document", "Medical"
    if any(k in lower for k in ("resume", "curriculum vitae", "experience", "education", "skills", "projects", "work experience", "university")):
        return "Resume / CV", "Personal"
    if any(k in lower for k in ("http", "localhost", "error", "console", "terminal", "dashboard", "settings", "password", "username")):
        return "Application Screenshot", "Other"
    if len(ocr_text) >= 40:
        return "Scanned Document / Text Image", "Other"
    return "Photograph / Visual Image", "Other"


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
            parsed["_engine"] = f"gemini:{model}"
            return parsed
    except Exception as exc:
        logger.warning("Gemini VLM call failed (%s); falling back to local Tesseract.", exc)
    return None


async def _try_anthropic_text_summary(
    text: str, filename: str, user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Ultra-low-cost, high-speed document classification, summary, and OCR quality evaluation.
    Sends only text (~150-300 tokens) costing ~$0.00007.
    Evaluates whether the extracted text is clear/legible or garbled/unclear.
    """
    api_key = (settings.ANTHROPIC_API_KEY or "").strip()
    if not api_key:
        return None

    clean_text = (text or "").strip()
    if len(clean_text) < 15:
        return None

    model = settings.ANTHROPIC_MODEL or "claude-haiku-4-5-20251001"
    prompt = f"""You are an intelligent document analyzer and OCR quality evaluator for a secure personal document vault.
Analyze the following text extracted via local OCR from '{filename}'.

Evaluate whether the extracted text is clear, legible, and meaningful:
- Set "is_text_clear": true ONLY if the text contains clear, legible, coherent sentences or valid structured fields that accurately represent the document.
- Set "is_text_clear": false if the text contains noisy artifacts, garbled/corrupted characters, fragmented symbols, or if critical document text (like names, IDs, numbers, addresses) appears scrambled, incomplete, or illegible.

Return ONLY valid JSON (no markdown formatting, no code fences, no extra text) with these exact keys:
{{
  "is_text_clear": true or false,
  "clarity_reason": "Crisp 1-sentence explanation of why the text is clear or unclear",
  "document_type": "Specific human-readable label (e.g. 'PAN Card', 'Aadhaar Card', 'Passport', 'Resume / CV', 'Tax Invoice / Bill', 'Identity Document', 'Medical Report', 'Bank Statement', 'Employment Contract')",
  "summary": "1-2 crisp, professional sentences explaining what this document is about, key subject/entity, and core details.",
  "category_hint": "One of: 'Identity', 'Financial', 'Medical', 'Personal', 'Other'"
}}

Extracted Text:
{clean_text[:4000]}"""

    try:
        raw_text, token_info = await call_claude_messages(
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            call_type="ocr_quality_eval",
            model=model,
            max_tokens=250,
            temperature=0.1,
            timeout_sec=20.0,
        )
        parsed = _extract_json_block(raw_text)
        if parsed and parsed.get("summary"):
            parsed["_engine"] = f"anthropic:{model}"
            parsed["_token_info"] = token_info
            return parsed
    except Exception as exc:
        logger.warning("Anthropic Haiku text call failed (%s); falling back to vision escalation.", exc)
    return None


async def _try_anthropic_vision_summary(
    jpeg_bytes: bytes, filename: str, user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    High-fidelity Claude Haiku Vision OCR and document classification.
    Maintains high resolution (up to 1600px) so all text, IDs, codes, names, and tables are clearly legible.
    Logs call details to dedicated claude_chat.log and records tokens in token_usage.db.
    """
    api_key = (settings.ANTHROPIC_API_KEY or "").strip()
    if not api_key:
        return None

    # Maintain high resolution (up to 1600px) so fine document text and numbers are sharp
    try:
        with Image.open(io.BytesIO(jpeg_bytes)) as raw_img:
            thumb = raw_img.copy()
            if max(thumb.width, thumb.height) > 1600:
                thumb.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            thumb_buf = io.BytesIO()
            thumb.convert("RGB").save(thumb_buf, format="JPEG", quality=90)
            b64_data = base64.b64encode(thumb_buf.getvalue()).decode("ascii")
    except Exception as exc:
        logger.warning("Failed to prepare image for Haiku Vision: %s", exc)
        b64_data = base64.b64encode(jpeg_bytes).decode("ascii")

    model = settings.ANTHROPIC_MODEL or "claude-haiku-4-5-20251001"
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64_data,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"Analyze this image from '{filename}' for a secure personal document vault.\n"
                        "1. Extract ALL readable printed and handwritten text verbatim into 'visible_text' "
                        "(names, numbers, IDs, dates, addresses, codes, labels, table rows, and headers). "
                        "Do not omit any visible text.\n"
                        "2. Provide a 1-2 sentence crisp 'summary' of what this document or image is about.\n"
                        "3. Specify 'document_type' (e.g. 'Identity Document / Card', 'Passport', 'Tax Invoice / Bill', "
                        "'Medical Prescription / Report', 'Certificate', 'Bank Statement', 'Photograph', 'Diagram').\n"
                        "4. Specify 'category_hint' ('Identity', 'Financial', 'Medical', 'Personal', 'Other').\n\n"
                        "Return ONLY a JSON object with keys: summary, visible_text, document_type, category_hint."
                    ),
                },
            ],
        }
    ]

    try:
        raw_text, token_info = await call_claude_messages(
            messages=messages,
            user_id=user_id,
            call_type="vision_summary",
            model=model,
            max_tokens=600,
            temperature=0.1,
            timeout_sec=30.0,
        )
        parsed = _extract_json_block(raw_text)
        if parsed and (parsed.get("summary") or parsed.get("visible_text")):
            # If visible_text was returned as a list of strings, join with newlines
            raw_vis = parsed.get("visible_text")
            if isinstance(raw_vis, list):
                parsed["visible_text"] = "\n".join(str(item) for item in raw_vis if item)
            elif raw_vis is not None:
                parsed["visible_text"] = str(raw_vis).strip()
            else:
                parsed["visible_text"] = ""
            parsed["_engine"] = f"anthropic:{model}"
            parsed["_token_info"] = token_info
            return parsed
    except Exception as exc:
        logger.warning("Anthropic Haiku vision call failed (%s); falling back to local profiler.", exc)
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
            parsed["_engine"] = f"ollama:{model}"
            return parsed
    except Exception as exc:
        logger.warning("Ollama VLM call failed (%s); falling back to local Tesseract.", exc)
    return None


async def analyze_image(
    image_bytes: bytes, filename: str, user_id: Optional[str] = None
) -> VisionResult:
    """
    Intelligent Hybrid OCR & Vision Escalation Pipeline:
    1. Run local English Tesseract OCR on the image ($0 cost, 0 API tokens).
    2. If Tesseract extracts text, send the text to Claude Haiku to evaluate quality (~$0.00007):
       - If AI determines the text IS clear and legible:
         Uses Tesseract text + AI summary (saving 100% of image token costs).
       - If AI determines the text is NOT clear (noisy artifacts, garbled/corrupted characters,
         missing IDs/names, or illegible), or if Tesseract extracted < 3 words:
         AUTOMATICALLY escalates to Claude Haiku Vision, sending the image directly for a
         high-resolution, detailed description and verbatim text extraction!
    3. If vision escalation is triggered, all visible text and details are extracted verbatim into visible_text.
    """
    clean_img, jpeg_bytes, orig_format, orig_size, exif_meta = await asyncio.to_thread(
        _sanitize_image_to_jpeg, image_bytes
    )
    w, h = orig_size

    # 1. Local Tesseract OCR (Free, $0 cost)
    ocr_text = await asyncio.to_thread(_run_tesseract_english_sync, clean_img)
    clean_ocr = _clean_ocr_text(ocr_text)
    word_count = len(re.findall(r"[A-Za-z0-9]{2,}", clean_ocr))
    orientation = "landscape" if w > h * 1.15 else ("portrait" if h > w * 1.15 else "square")

    needs_direct_vision = False
    haiku_eval = None

    if word_count >= 3:
        # Ask AI model to evaluate whether the extracted OCR text is clear & legible (~$0.00007)
        haiku_eval = await _try_anthropic_text_summary(clean_ocr, filename, user_id=user_id)
        if haiku_eval:
            is_clear = haiku_eval.get("is_text_clear")
            # If AI explicitly says text is not clear, or summary indicates corruption/illegibility:
            if is_clear is False:
                logger.info(
                    "AI evaluation determined OCR text for '%s' is not clear (%s). Escalating to Claude Haiku Vision.",
                    filename,
                    haiku_eval.get("clarity_reason"),
                )
                needs_direct_vision = True
            elif is_clear is True:
                needs_direct_vision = False
            else:
                summary_lower = (haiku_eval.get("summary") or "").lower()
                if any(kw in summary_lower for kw in ["corrupt", "illegible", "unreadable", "scrambled", "fragmented characters", "unable to determine"]):
                    needs_direct_vision = True
        else:
            if word_count < 8:
                needs_direct_vision = True
    else:
        # Fewer than 3 words: photos, headshots, or text missed by Tesseract -> send image to AI vision
        needs_direct_vision = True

    # 2. If AI model said document extracted text is NOT clear (or image has no OCR text):
    # Send image DIRECTLY to Claude Haiku Vision for high-resolution detailed extraction and description!
    if needs_direct_vision:
        vision_res = await _try_anthropic_vision_summary(jpeg_bytes, filename, user_id=user_id)
        if vision_res:
            vis_text = (vision_res.get("visible_text") or "").strip()
            summary = (vision_res.get("summary") or f"{orig_format} Image").strip()
            doc_type = (vision_res.get("document_type") or f"{orig_format} Document").strip()
            cat_hint = vision_res.get("category_hint")
            engine = f"anthropic-vision-escalated:{vision_res.get('_engine', 'haiku-vision')}"

            # If vision extracted text, combine verbatim text + detailed summary
            if vis_text:
                combined = f"[Extracted Text]\n{vis_text}\n\n[Document Summary]\n{summary}"
            else:
                combined = f"[Image Summary]\n{summary}"

            return VisionResult(
                summary=summary,
                visible_text=vis_text,
                combined_text=combined,
                document_type=doc_type,
                category_hint=cat_hint if cat_hint in {"Identity", "Financial", "Medical", "Personal", "Other"} else None,
                engine=engine,
                width=w,
                height=h,
                image_format=orig_format,
            )

    # 3. If AI model confirmed text IS clear:
    if haiku_eval:
        summary = haiku_eval.get("summary") or f"Document image containing {word_count} extracted words."
        doc_type = haiku_eval.get("document_type") or f"{orig_format} Document"
        cat_hint = haiku_eval.get("category_hint")
        engine = f"tesseract-ocr+{haiku_eval.get('_engine', 'haiku-text')}"
        combined = f"[Extracted Text]\n{clean_ocr}\n\n[Document Summary]\n{summary}"

        return VisionResult(
            summary=summary,
            visible_text=clean_ocr,
            combined_text=combined,
            document_type=doc_type,
            category_hint=cat_hint if cat_hint in {"Identity", "Financial", "Medical", "Personal", "Other"} else None,
            engine=engine,
            width=w,
            height=h,
            image_format=orig_format,
        )

    # 4. Fallback if no AI response: Local profiler + Tesseract text
    doc_type, category_hint = _infer_document_type_and_category(clean_ocr, filename)
    stat = ImageStat.Stat(clean_img)
    brightness = sum(stat.mean[:3]) / 3.0
    tone = "light-background" if brightness > 205 else ("dark-themed" if brightness < 70 else "color")
    if clean_ocr:
        summary = f"{doc_type} ({orig_format}, ~{word_count} words extracted via Tesseract OCR)."
        combined = f"[Extracted Text]\n{clean_ocr}\n\n[Document Summary]\n{summary}"
    else:
        summary = f"{doc_type}: {orientation} {orig_format} ({w}x{h}px, {tone}). No printed text detected."
        combined = f"[Image Summary]\n{summary}"

    return VisionResult(
        summary=summary,
        visible_text=clean_ocr,
        combined_text=combined,
        document_type=doc_type,
        category_hint=category_hint,
        engine="tesseract-ocr-fallback",
        width=w,
        height=h,
        image_format=orig_format,
    )


async def summarize_text_document(
    text: str, filename: str, doc_type: str, page_count: int, user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate an intelligent, human-like summary and precise document classification.
    1. Tries ultra-low-cost Claude Haiku text input (~$0.00007).
    2. Falls back to local intelligent document profiler if API key is not configured or offline.
    """
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    if not clean:
        return {
            "summary": f"{doc_type} ({filename}, {page_count} page{'s' if page_count != 1 else ''}) verified and stored securely.",
            "doc_type": doc_type,
            "category_hint": None,
            "engine": "local-empty",
        }

    # 1. Low-cost Claude Haiku Text Summary
    haiku_res = await _try_anthropic_text_summary(clean, filename, user_id=user_id)
    if haiku_res:
        resolved_doc = str(haiku_res.get("document_type") or doc_type).strip()
        summary_text = str(haiku_res.get("summary") or "").strip()
        cat = haiku_res.get("category_hint")
        cat_hint = cat if cat in {"Identity", "Financial", "Medical", "Personal", "Other"} else None
        return {
            "summary": summary_text,
            "doc_type": resolved_doc,
            "category_hint": cat_hint,
            "engine": haiku_res.get("_engine", "anthropic-haiku"),
        }

    # 2. Local Fallback: Intelligent Keyword Profiler
    inferred_type, inferred_cat = _infer_document_type_and_category(clean, filename)
    if inferred_type.endswith(" (Image)"):
        inferred_type = inferred_type.replace(" (Image)", "")

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

    summary = f"{inferred_type}: {snippet}"
    return {
        "summary": summary,
        "doc_type": inferred_type,
        "category_hint": inferred_cat,
        "engine": "local-profiler",
    }
