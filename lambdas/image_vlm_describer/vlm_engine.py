"""
Isolated Vision-Language Model (VLM) Engine for Lambda 3 (MicroVM Sandbox).

Responsibilities:
1. Safely decode & sanitize untrusted images (decompression bomb protection,
   EXIF stripping, RGB conversion, proportional downscaling to MAX_IMAGE_DIM).
2. Run a lightweight VLM to produce:
   - `visual_description`: Rich semantic description of what the image shows.
   - `visible_text`: Any readable printed or handwritten text visible in the image.
   - `combined_text`: Unified text fed downstream into Lambda 2 (ML Security + pgvector).
3. Supports two execution modes:
   - `embedded` (default for AWS Firecracker microVM): Loads HuggingFaceTB/SmolVLM-500M-Instruct
     locally on CPU from baked `/opt/models/vlm` or HuggingFace cache.
   - `ollama` (fast Apple Metal GPU option for local Mac dev): Sends sanitized base64 image
     to local Ollama server (`host.docker.internal:11434`).
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Guard against decompression bombs (malicious tiny PNGs expanding to gigabytes in RAM)
Image.MAX_IMAGE_PIXELS = 25_000_000

VLM_PROMPT = (
    "Analyze this image thoroughly for a personal document vault index. "
    "Respond ONLY in valid JSON with keys: "
    '"visual_description" (2-4 clear sentences describing what this image is about, its layout, objects, charts, or document type), '
    '"visible_text" (verbatim transcription of any readable text, numbers, dates, or handwriting; empty string if none), and '
    '"document_category_hint" (one of: Identity, Medical, Financial, Personal, Diagram, Photo, Other).'
)

# Module-level cache across warm Lambda invocations
_CACHED_PROCESSOR = None
_CACHED_MODEL = None


@dataclass
class VLMResult:
    visual_description: str
    visible_text: str
    combined_text: str
    document_category_hint: str
    model_used: str
    image_width: int
    image_height: int
    image_format: str


def sanitize_image(image_bytes: bytes, max_dim: Optional[int] = None) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Decode image safely, strip EXIF/metadata, apply EXIF orientation, convert to RGB,
    and resize proportionally to fit within `max_dim x max_dim`.
    """
    limit = int(max_dim or os.getenv("MAX_IMAGE_DIM", "1024"))
    with Image.open(io.BytesIO(image_bytes)) as raw_img:
        orig_format = raw_img.format or "UNKNOWN"
        img = ImageOps.exif_transpose(raw_img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Re-encode into clean RGB image without any embedded EXIF/XMP metadata
        if max(img.width, img.height) > limit:
            img.thumbnail((limit, limit), Image.Resampling.LANCZOS)

        clean_img = Image.new("RGB", img.size)
        clean_img.paste(img)

    meta = {
        "width": clean_img.width,
        "height": clean_img.height,
        "format": orig_format,
    }
    return clean_img, meta


def _parse_vlm_json_output(raw_text: str) -> Tuple[str, str, str]:
    """Parse structured JSON from VLM output with resilient plain-text fallback."""
    text = (raw_text or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            desc = str(parsed.get("visual_description", "")).strip()
            visible = str(parsed.get("visible_text", "")).strip()
            cat = str(parsed.get("document_category_hint", "Other")).strip() or "Other"
            if desc or visible:
                return desc, visible, cat
        except json.JSONDecodeError:
            pass
    return text, "", "Other"


def _build_combined_text(visual_description: str, visible_text: str) -> str:
    sections = []
    if visual_description:
        sections.append(f"[Visual Description]\n{visual_description}")
    if visible_text:
        sections.append(f"[Visible Text]\n{visible_text}")
    return "\n\n".join(sections).strip()


def _run_ollama_vlm(clean_img: Image.Image) -> Tuple[str, str]:
    """Call local Ollama server (Metal-accelerated on Apple Silicon) for fast dev inference."""
    import httpx

    ollama_url = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
    model_name = os.getenv("OLLAMA_MODEL", "moondream")

    buf = io.BytesIO()
    clean_img.save(buf, format="JPEG", quality=88)
    b64_img = base64.b64encode(buf.getvalue()).decode("ascii")

    resp = httpx.post(
        f"{ollama_url}/api/generate",
        json={
            "model": model_name,
            "prompt": VLM_PROMPT,
            "images": [b64_img],
            "stream": False,
        },
        timeout=90.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return str(data.get("response", "")).strip(), f"ollama/{model_name}"


def _run_embedded_vlm(clean_img: Image.Image) -> Tuple[str, str]:
    """
    Run embedded SmolVLM-500M-Instruct locally on CPU inside the Lambda microVM.
    """
    global _CACHED_PROCESSOR, _CACHED_MODEL

    import torch
    from transformers import AutoModelForVision2Seq, AutoProcessor

    model_dir = os.getenv("VLM_MODEL_DIR", "/opt/models/vlm")
    model_id = os.getenv("VLM_MODEL_ID", "HuggingFaceTB/SmolVLM-500M-Instruct")
    source = model_dir if os.path.isdir(model_dir) and os.listdir(model_dir) else model_id

    if _CACHED_PROCESSOR is None or _CACHED_MODEL is None:
        logger.info("Loading embedded VLM from %s...", source)
        _CACHED_PROCESSOR = AutoProcessor.from_pretrained(source)
        _CACHED_MODEL = AutoModelForVision2Seq.from_pretrained(
            source,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
        )
        _CACHED_MODEL.eval()

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": VLM_PROMPT},
            ],
        }
    ]
    prompt = _CACHED_PROCESSOR.apply_chat_template(messages, add_generation_prompt=True)
    inputs = _CACHED_PROCESSOR(text=prompt, images=[clean_img], return_tensors="pt")

    with torch.no_grad():
        generated_ids = _CACHED_MODEL.generate(**inputs, max_new_tokens=320, do_sample=False)

    # Decode only newly generated tokens
    input_len = inputs["input_ids"].shape[1]
    decoded = _CACHED_PROCESSOR.batch_decode(
        generated_ids[:, input_len:], skip_special_tokens=True
    )[0]
    return decoded.strip(), model_id


def describe_image(image_bytes: bytes, vlm_mode: Optional[str] = None) -> VLMResult:
    """Sanitize image and produce a rich VLM visual description + visible text transcription."""
    clean_img, meta = sanitize_image(image_bytes)
    mode = (vlm_mode or os.getenv("VLM_MODE", "embedded")).lower().strip()

    if mode == "ollama":
        raw_output, model_used = _run_ollama_vlm(clean_img)
    elif mode == "mock":
        # Lightweight deterministic mode for fast CI / unit testing without weights
        raw_output = json.dumps(
            {
                "visual_description": (
                    f"Sanitized {meta['format']} image ({meta['width']}x{meta['height']}px) "
                    "analyzed in isolated VLM microVM sandbox."
                ),
                "visible_text": "",
                "document_category_hint": "Photo",
            }
        )
        model_used = "vlm-mock-local"
    else:
        raw_output, model_used = _run_embedded_vlm(clean_img)

    desc, visible, cat = _parse_vlm_json_output(raw_output)
    combined = _build_combined_text(desc, visible)

    return VLMResult(
        visual_description=desc,
        visible_text=visible,
        combined_text=combined,
        document_category_hint=cat,
        model_used=model_used,
        image_width=meta["width"],
        image_height=meta["height"],
        image_format=meta["format"],
    )
