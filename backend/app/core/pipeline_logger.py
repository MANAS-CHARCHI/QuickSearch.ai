"""
Structured File Security & Ingestion Pipeline Logger.

Writes every stage of the file lifecycle (upload -> quarantine -> SHA-256 integrity ->
ClamAV virus scan -> Vision/OCR summary -> SQLi & Prompt-Injection gate -> secured S3 ->
pgvector indexing -> view/download/delete) simultaneously to:
1. Container stdout (`docker logs -f vault_backend`)
2. Host-mounted human-readable rotating log (`<FILE_LOG_DIR>/file_pipeline.log`)
3. Host-mounted structured JSONL log (`<FILE_LOG_DIR>/file_pipeline.jsonl`)
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from typing import Any, Dict, Optional

from app.core.config import settings

_LOGGER_NAME = "vaultcity.file_pipeline"
_JSONL_LOGGER_NAME = "vaultcity.file_pipeline.jsonl"
_CONFIGURED = False


def _ensure_log_dir(path: str) -> Optional[str]:
    try:
        os.makedirs(path, exist_ok=True)
        # Verify writable
        probe = os.path.join(path, ".write_probe")
        with open(probe, "a", encoding="utf-8"):
            pass
        try:
            os.remove(probe)
        except OSError:
            pass
        return path
    except OSError:
        return None


def _setup_loggers() -> tuple[logging.Logger, logging.Logger]:
    global _CONFIGURED
    text_logger = logging.getLogger(_LOGGER_NAME)
    jsonl_logger = logging.getLogger(_JSONL_LOGGER_NAME)

    if _CONFIGURED:
        return text_logger, jsonl_logger

    text_logger.setLevel(logging.INFO)
    text_logger.propagate = False
    jsonl_logger.setLevel(logging.INFO)
    jsonl_logger.propagate = False

    # 1. Always emit readable logs to stdout so `docker logs vault_backend` captures them
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | [FILE-PIPELINE] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    text_logger.addHandler(stdout_handler)

    # 2. Emit to host-mounted folder (./logs on host -> /app/logs in container)
    log_dir = _ensure_log_dir(settings.FILE_LOG_DIR) or _ensure_log_dir("/tmp/vaultcity_logs")
    if log_dir:
        text_log_path = os.path.join(log_dir, "file_pipeline.log")
        file_handler = RotatingFileHandler(
            text_log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
        )
        text_logger.addHandler(file_handler)

        jsonl_log_path = os.path.join(log_dir, "file_pipeline.jsonl")
        jsonl_handler = RotatingFileHandler(
            jsonl_log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        jsonl_handler.setLevel(logging.INFO)
        jsonl_handler.setFormatter(logging.Formatter("%(message)s"))
        jsonl_logger.addHandler(jsonl_handler)

    _CONFIGURED = True
    return text_logger, jsonl_logger


def log_file_event(
    stage: str,
    status: str,
    message: str,
    *,
    file_id: Optional[str] = None,
    user_id: Optional[str] = None,
    filename: Optional[str] = None,
    duration_ms: Optional[float] = None,
    details: Optional[Dict[str, Any]] = None,
    level: str = "INFO",
) -> None:
    """Emit a single pipeline event to docker stdout + host .log + host .jsonl."""
    text_logger, jsonl_logger = _setup_loggers()

    fid = str(file_id) if file_id else "-"
    uid = str(user_id) if user_id else "-"
    fname = filename or "-"
    dur = f" ({duration_ms:.1f}ms)" if duration_ms is not None else ""
    extra_kv = ""
    if details:
        compact = json.dumps(details, default=str, ensure_ascii=False)
        extra_kv = f" | details={compact}"

    line = f"stage={stage} status={status} file_id={fid} user_id={uid} file={fname!r}{dur} | {message}{extra_kv}"
    log_fn = getattr(text_logger, level.lower(), text_logger.info)
    log_fn(line)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "stage": stage,
        "status": status,
        "file_id": file_id,
        "user_id": user_id,
        "filename": filename,
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "message": message,
        "details": details or {},
    }
    jsonl_logger.info(json.dumps(record, default=str, ensure_ascii=False))
