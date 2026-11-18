"""
ML SQL Injection Scanner for Lambda 2 (Sliding Window ONNX Classifier + Structural Guard).

Model: `cssupport/mobilebert-sql-injection-detect` (exported to ONNX in `/opt/models/sqli`).
Runs over overlapping text windows so SQLi payloads buried deep inside long documents
cannot bypass model sequence length limits.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CACHED_SQLI_PIPELINE = None
_SQLI_LOAD_ATTEMPTED = False

# High-precision structural SQLi indicators (used both for audit explainability & offline fallback)
SQLI_PATTERNS: List[Tuple[str, re.Pattern, float]] = [
    (
        "union_select",
        re.compile(r"\bUNION\s+(?:ALL\s+)?SELECT\b", re.IGNORECASE),
        0.95,
    ),
    (
        "stacked_ddl_dml",
        re.compile(
            r";\s*(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)|DELETE\s+FROM|TRUNCATE\s+TABLE|ALTER\s+TABLE|INSERT\s+INTO|UPDATE\s+\w+\s+SET)\b",
            re.IGNORECASE,
        ),
        0.96,
    ),
    (
        "boolean_tautology",
        re.compile(
            r"(?:'|\"|\b)\s*OR\s+(?:'?\d+'?\s*=\s*'?\d+'?|TRUE)\s*(?:--|#|/\*|$)",
            re.IGNORECASE,
        ),
        0.92,
    ),
    (
        "time_based_blind",
        re.compile(
            r"\b(?:PG_SLEEP|SLEEP|WAITFOR\s+DELAY|BENCHMARK)\s*\(",
            re.IGNORECASE,
        ),
        0.94,
    ),
    (
        "system_catalog_probe",
        re.compile(
            r"\b(?:INFORMATION_SCHEMA\.(?:TABLES|COLUMNS)|PG_CATALOG\.PG_TABLES|XP_CMDSHELL|LOAD_FILE\s*\()\b",
            re.IGNORECASE,
        ),
        0.91,
    ),
    (
        "quote_comment_injection",
        re.compile(r"'\s*(?:OR|AND)\s+'[^']*'\s*=\s*'[^']*'", re.IGNORECASE),
        0.90,
    ),
]


@dataclass
class ScanReport:
    scanner: str
    is_blocked: bool
    max_score: float
    threshold: float
    engine: str
    flagged_windows: List[Dict] = field(default_factory=list)


def build_sliding_windows(text: str, window_chars: int = 512, stride: int = 384) -> List[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= window_chars:
        return [cleaned]
    windows: List[str] = []
    pos = 0
    while pos < len(cleaned):
        windows.append(cleaned[pos : pos + window_chars])
        if pos + window_chars >= len(cleaned):
            break
        pos += stride
    return windows


def _load_onnx_sqli_classifier():
    global _CACHED_SQLI_PIPELINE, _SQLI_LOAD_ATTEMPTED
    if _SQLI_LOAD_ATTEMPTED:
        return _CACHED_SQLI_PIPELINE
    _SQLI_LOAD_ATTEMPTED = True

    if os.getenv("DISABLE_ML_MODELS", "false").lower() == "true":
        return None

    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer, pipeline

        cache_dir = os.getenv("MODEL_CACHE_DIR", "/opt/models")
        local_dir = os.path.join(cache_dir, "sqli")
        model_id = os.getenv("SQLI_MODEL_ID", "cssupport/mobilebert-sql-injection-detect")

        if os.path.isdir(local_dir) and os.listdir(local_dir):
            tokenizer = AutoTokenizer.from_pretrained(local_dir)
            model = ORTModelForSequenceClassification.from_pretrained(local_dir)
        else:
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = ORTModelForSequenceClassification.from_pretrained(model_id, export=True)

        _CACHED_SQLI_PIPELINE = pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            truncation=True,
            max_length=512,
        )
        return _CACHED_SQLI_PIPELINE
    except Exception as exc:
        logger.warning("SQLi ONNX model unavailable (%s); using structural fallback.", exc)
        return None


def _structural_sqli_score(window: str) -> Tuple[float, List[str]]:
    score = 0.0
    matched: List[str] = []
    for name, pattern, weight in SQLI_PATTERNS:
        if pattern.search(window):
            matched.append(name)
            score = max(score, weight)
    return score, matched


def _ml_sqli_score(clf, window: str) -> float:
    out = clf(window)[0]
    label = str(out.get("label", "")).upper()
    raw_score = float(out.get("score", 0.0))
    # MobileBERT SQLi model labels: LABEL_1 / SQLI / INJECTION / MALICIOUS = positive
    if any(tok in label for tok in ("1", "SQL", "INJECT", "MALIC", "UNSAFE")):
        return raw_score
    return 1.0 - raw_score


def scan_sql_injection(
    text: str,
    extra_snippets: Optional[List[str]] = None,
    threshold: Optional[float] = None,
) -> ScanReport:
    """
    Scan text (+ any decoded base64 snippets) for SQL injection attacks.
    """
    cutoff = float(
        threshold if threshold is not None else os.getenv("SQLI_THRESHOLD", "0.80")
    )
    windows = build_sliding_windows(text)
    if extra_snippets:
        windows.extend(extra_snippets)

    clf = _load_onnx_sqli_classifier()
    engine = "onnx-mobilebert+structural" if clf is not None else "structural-fallback"

    max_score = 0.0
    flagged: List[Dict] = []

    for idx, win in enumerate(windows):
        struct_score, rules = _structural_sqli_score(win)
        ml_score = _ml_sqli_score(clf, win) if clf is not None else 0.0
        combined = max(ml_score, struct_score)
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
        scanner="sql_injection",
        is_blocked=max_score >= cutoff,
        max_score=round(max_score, 4),
        threshold=cutoff,
        engine=engine,
        flagged_windows=flagged[:5],
    )
