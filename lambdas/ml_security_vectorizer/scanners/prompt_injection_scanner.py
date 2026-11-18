"""
ML AI Prompt Injection & Manipulator Text Scanner for Lambda 2.

Model: `ProtectAI/deberta-v3-small-prompt-injection-v2` (exported to ONNX in
`/opt/models/prompt_injection`).
Detects indirect RAG prompt injection, instruction overrides, system prompt exfiltration,
jailbreaks, and visual prompt injections originating from VLM-described images.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from .sqli_scanner import ScanReport, build_sliding_windows

logger = logging.getLogger(__name__)

_CACHED_PI_PIPELINE = None
_PI_LOAD_ATTEMPTED = False

# High-precision AI manipulator / prompt injection indicators (audit explainability & fallback)
PROMPT_INJECTION_PATTERNS: List[Tuple[str, re.Pattern, float]] = [
    (
        "instruction_override",
        re.compile(
            r"\b(?:ignore|disregard|forget|override|bypass)\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier|system)\s+(?:instructions|prompts|rules|directions|guidelines)\b",
            re.IGNORECASE,
        ),
        0.96,
    ),
    (
        "system_prompt_exfiltration",
        re.compile(
            r"\b(?:reveal|print|dump|output|show|leak|repeat)\s+(?:your\s+|the\s+)?(?:system\s+prompt|hidden\s+instructions|initial\s+prompt|secret\s+instructions|api\s+keys?)\b",
            re.IGNORECASE,
        ),
        0.95,
    ),
    (
        "role_hijack_jailbreak",
        re.compile(
            r"\b(?:you\s+are\s+now\s+(?:in\s+)?(?:DAN|developer|unrestricted|jailbreak|admin)\s+mode|act\s+as\s+an?\s+unrestricted\s+AI|new\s+system\s+instruction)\b",
            re.IGNORECASE,
        ),
        0.94,
    ),
    (
        "chat_template_delimiter_injection",
        re.compile(
            r"(?:<\|im_start\|>\s*system|<\|system\|>|\[INST\]|<<SYS>>|###\s*System\s*:)",
            re.IGNORECASE,
        ),
        0.93,
    ),
    (
        "rag_data_exfiltration",
        re.compile(
            r"\b(?:send|exfiltrate|forward|post)\s+(?:all\s+)?(?:user|vault|private|confidential)\s+(?:documents|data|files|records|secrets)\s+to\b",
            re.IGNORECASE,
        ),
        0.95,
    ),
]


def _load_onnx_prompt_injection_classifier():
    global _CACHED_PI_PIPELINE, _PI_LOAD_ATTEMPTED
    if _PI_LOAD_ATTEMPTED:
        return _CACHED_PI_PIPELINE
    _PI_LOAD_ATTEMPTED = True

    if os.getenv("DISABLE_ML_MODELS", "false").lower() == "true":
        return None

    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer, pipeline

        cache_dir = os.getenv("MODEL_CACHE_DIR", "/opt/models")
        local_dir = os.path.join(cache_dir, "prompt_injection")
        model_id = os.getenv(
            "PROMPT_INJECTION_MODEL_ID", "ProtectAI/deberta-v3-small-prompt-injection-v2"
        )

        if os.path.isdir(local_dir) and os.listdir(local_dir):
            tokenizer = AutoTokenizer.from_pretrained(local_dir)
            model = ORTModelForSequenceClassification.from_pretrained(local_dir)
        else:
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = ORTModelForSequenceClassification.from_pretrained(model_id, export=True)

        _CACHED_PI_PIPELINE = pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            truncation=True,
            max_length=512,
        )
        return _CACHED_PI_PIPELINE
    except Exception as exc:
        logger.warning(
            "Prompt injection ONNX model unavailable (%s); using structural fallback.", exc
        )
        return None


def _structural_pi_score(window: str) -> Tuple[float, List[str]]:
    score = 0.0
    matched: List[str] = []
    for name, pattern, weight in PROMPT_INJECTION_PATTERNS:
        if pattern.search(window):
            matched.append(name)
            score = max(score, weight)
    return score, matched


def _ml_pi_score(clf, window: str) -> float:
    out = clf(window)[0]
    label = str(out.get("label", "")).upper()
    raw_score = float(out.get("score", 0.0))
    # ProtectAI DeBERTa labels: INJECTION vs SAFE (or LABEL_1 vs LABEL_0)
    if any(tok in label for tok in ("INJECT", "MALIC", "UNSAFE", "1")):
        return raw_score
    return 1.0 - raw_score


def scan_prompt_injection(
    text: str,
    extra_snippets: Optional[List[str]] = None,
    obfuscation_flagged: bool = False,
    threshold: Optional[float] = None,
) -> ScanReport:
    """
    Scan text (+ any decoded base64 snippets) for AI prompt injection / manipulator payloads.
    """
    cutoff = float(
        threshold
        if threshold is not None
        else os.getenv("PROMPT_INJECTION_THRESHOLD", "0.80")
    )
    windows = build_sliding_windows(text)
    if extra_snippets:
        windows.extend(extra_snippets)

    clf = _load_onnx_prompt_injection_classifier()
    engine = "onnx-deberta-v3+structural" if clf is not None else "structural-fallback"

    max_score = 0.0
    flagged: List[Dict] = []

    for idx, win in enumerate(windows):
        struct_score, rules = _structural_pi_score(win)
        ml_score = _ml_pi_score(clf, win) if clf is not None else 0.0
        combined = max(ml_score, struct_score)
        if obfuscation_flagged and combined > 0.4:
            combined = min(1.0, combined + 0.25)

        if combined > max_score:
            max_score = combined

        if combined >= cutoff:
            flagged.append(
                {
                    "window_index": idx,
                    "score": round(combined, 4),
                    "ml_score": round(ml_score, 4),
                    "matched_rules": rules,
                    "snippet": win[:160],
                }
            )

    return ScanReport(
        scanner="prompt_injection",
        is_blocked=max_score >= cutoff,
        max_score=round(max_score, 4),
        threshold=cutoff,
        engine=engine,
        flagged_windows=flagged[:5],
    )
