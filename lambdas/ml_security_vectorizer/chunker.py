"""
Recursive Semantic Text Chunker for Lambda 2.

Splits security-verified text along natural boundaries (paragraphs -> lines -> sentences -> words)
while maintaining configurable overlap and preserving page-level & VLM source metadata.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


@dataclass
class TextChunk:
    chunk_index: int
    page_number: int
    content: str
    source_type: str = "text"


def _split_recursive(text: str, chunk_size: int, separators: List[str]) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size or not separators:
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep = separators[0]
    if sep == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    parts = text.split(sep)
    if len(parts) == 1:
        return _split_recursive(text, chunk_size, separators[1:])

    merged: List[str] = []
    current = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        candidate = f"{current}{sep}{piece}" if current else piece
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                merged.append(current)
            if len(piece) > chunk_size:
                merged.extend(_split_recursive(piece, chunk_size, separators[1:]))
                current = ""
            else:
                current = piece
    if current:
        merged.append(current)
    return merged


def _apply_overlap(segments: List[str], chunk_overlap: int, chunk_size: int) -> List[str]:
    if chunk_overlap <= 0 or len(segments) <= 1:
        return segments
    out: List[str] = [segments[0]]
    for seg in segments[1:]:
        prev = out[-1]
        prefix = prev[-chunk_overlap:].lstrip()
        combined = f"{prefix} {seg}".strip()
        if len(combined) <= chunk_size + chunk_overlap:
            out.append(combined)
        else:
            out.append(seg)
    return out


def chunk_document(
    extracted_text: str,
    pages: Optional[List[Dict[str, Any]]] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[TextChunk]:
    """
    Split a document into overlapping chunks preserving page_number and source_type.
    """
    size = int(chunk_size or os.getenv("CHUNK_SIZE", "1000"))
    overlap = int(chunk_overlap if chunk_overlap is not None else os.getenv("CHUNK_OVERLAP", "150"))

    chunks: List[TextChunk] = []
    global_idx = 0

    if pages:
        for page in pages:
            page_text = (page.get("text") or "").strip()
            if not page_text:
                continue
            page_num = int(page.get("page_number", 1))
            src_type = str(page.get("source_type", "text"))
            raw_segments = _split_recursive(page_text, size, SEPARATORS)
            overlapped = _apply_overlap(raw_segments, overlap, size)
            for seg in overlapped:
                chunks.append(
                    TextChunk(
                        chunk_index=global_idx,
                        page_number=page_num,
                        content=seg,
                        source_type=src_type,
                    )
                )
                global_idx += 1
    elif extracted_text and extracted_text.strip():
        raw_segments = _split_recursive(extracted_text.strip(), size, SEPARATORS)
        overlapped = _apply_overlap(raw_segments, overlap, size)
        for seg in overlapped:
            chunks.append(
                TextChunk(
                    chunk_index=global_idx,
                    page_number=1,
                    content=seg,
                    source_type="text",
                )
            )
            global_idx += 1

    return chunks
