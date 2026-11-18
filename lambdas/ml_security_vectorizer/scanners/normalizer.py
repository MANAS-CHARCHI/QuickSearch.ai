"""
Text Normalizer & Obfuscation Pre-Filter for Lambda 2.

Detects:
- Invisible zero-width / bidi / Unicode tag smuggling characters often used to hide
  indirect prompt injections from human eyes while still executing on LLMs.
- Normalizes text with Unicode NFKC so homoglyph / full-width SQLi and prompt
  injection attacks are canonicalized before ML scanning.
"""
from __future__ import annotations

import base64
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List

# Zero-width, bidirectional override, and Unicode tag characters
INVISIBLE_CHARS_RE = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\U000e0000-\U000e007f]"
)

# Candidate base64 segments (>= 32 chars) that could smuggle hidden instructions
BASE64_CANDIDATE_RE = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9+/=])")


@dataclass
class NormalizationResult:
    normalized_text: str
    invisible_char_count: int = 0
    decoded_base64_snippets: List[str] = field(default_factory=list)
    obfuscation_flagged: bool = False


def normalize_and_inspect(raw_text: str) -> NormalizationResult:
    """
    Normalize text via NFKC, strip invisible obfuscation characters, and extract any
    printable base64-encoded strings so downstream ML scanners inspect decoded payloads too.
    """
    if not raw_text:
        return NormalizationResult(normalized_text="")

    invisible_matches = INVISIBLE_CHARS_RE.findall(raw_text)
    invisible_count = len(invisible_matches)

    stripped = INVISIBLE_CHARS_RE.sub("", raw_text)
    normalized = unicodedata.normalize("NFKC", stripped)

    decoded_snippets: List[str] = []
    for match in BASE64_CANDIDATE_RE.findall(normalized):
        if len(match) % 4 != 0:
            continue
        try:
            decoded_bytes = base64.b64decode(match, validate=True)
            decoded_str = decoded_bytes.decode("utf-8")
            printable_ratio = sum(ch.isprintable() or ch.isspace() for ch in decoded_str) / max(
                1, len(decoded_str)
            )
            if printable_ratio > 0.90 and len(decoded_str.strip()) >= 12:
                decoded_snippets.append(decoded_str.strip())
        except Exception:
            continue

    # Flag if excessive invisible smuggling chars were hidden in the text
    obfuscation_flagged = invisible_count >= 5

    return NormalizationResult(
        normalized_text=normalized.strip(),
        invisible_char_count=invisible_count,
        decoded_base64_snippets=decoded_snippets,
        obfuscation_flagged=obfuscation_flagged,
    )
