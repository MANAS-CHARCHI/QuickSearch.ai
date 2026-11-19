"""
Claude API Invocation, Token Tracking & Dedicated Usage Database.

Features:
1. Dedicated Log File:
   - Formatted human-readable audit log: `<FILE_LOG_DIR>/claude_chat.log`
   - High-throughput JSONL log: `<FILE_LOG_DIR>/claude_chat.jsonl`
   Records timestamp, user ID, model, call type, input tokens, output tokens,
   total tokens, duration, estimated cost, full prompt, and response.

2. Dedicated Metrics Database:
   - Standalone SQLite database: `<FILE_LOG_DIR>/token_usage.db`
   - Tracks every call with separate input and output token counts per user and per model.
   - Computes aggregated user statistics (total input, total output, total tokens, cost).
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.core.config import settings

logger = logging.getLogger("vaultcity.claude_tracker")

_TEXT_LOGGER_NAME = "vaultcity.claude_chat"
_JSONL_LOGGER_NAME = "vaultcity.claude_chat.jsonl"
_CONFIGURED = False

# Pricing per million tokens (USD)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    "claude-haiku-5-5": {"input": 0.25, "output": 1.25},
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-sonnet-5-5": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-opus-5-5": {"input": 15.00, "output": 75.00},
    "claude-fable-5-2": {"input": 1.00, "output": 5.00},
}
DEFAULT_PRICING = {"input": 0.25, "output": 1.25}


def _get_db_path() -> str:
    log_dir = settings.FILE_LOG_DIR or "/app/logs"
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "token_usage.db")


def _init_token_db() -> None:
    """Initialize dedicated SQLite database schema for token metrics."""
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path, timeout=10.0) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS claude_token_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    model TEXT NOT NULL,
                    call_type TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL NOT NULL DEFAULT 0.0,
                    duration_ms REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'success',
                    prompt_preview TEXT,
                    response_preview TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_records_user ON claude_token_records(user_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_records_model ON claude_token_records(model);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_records_created ON claude_token_records(created_at);
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_model_aggregates (
                    user_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    total_cost_usd REAL NOT NULL DEFAULT 0.0,
                    request_count INTEGER NOT NULL DEFAULT 0,
                    last_used_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, model)
                );
                """
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not initialize token SQLite database at %s: %s", db_path, exc)


def _setup_claude_loggers() -> Tuple[logging.Logger, logging.Logger]:
    global _CONFIGURED
    text_logger = logging.getLogger(_TEXT_LOGGER_NAME)
    jsonl_logger = logging.getLogger(_JSONL_LOGGER_NAME)

    if _CONFIGURED:
        return text_logger, jsonl_logger

    text_logger.setLevel(logging.INFO)
    text_logger.propagate = False
    jsonl_logger.setLevel(logging.INFO)
    jsonl_logger.propagate = False

    log_dir = settings.FILE_LOG_DIR or "/app/logs"
    os.makedirs(log_dir, exist_ok=True)

    text_log_path = os.path.join(log_dir, "claude_chat.log")
    file_handler = RotatingFileHandler(
        text_log_path,
        maxBytes=15 * 1024 * 1024,  # 15 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    text_logger.addHandler(file_handler)

    jsonl_log_path = os.path.join(log_dir, "claude_chat.jsonl")
    jsonl_handler = RotatingFileHandler(
        jsonl_log_path,
        maxBytes=15 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    jsonl_handler.setLevel(logging.INFO)
    jsonl_handler.setFormatter(logging.Formatter("%(message)s"))
    jsonl_logger.addHandler(jsonl_handler)

    _CONFIGURED = True
    return text_logger, jsonl_logger


USD_TO_INR_RATE: float = 86.0  # 1 USD ≈ ₹86.0 INR


# Initialize schema on module import
_init_token_db()


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD based on model pricing."""
    rates = MODEL_PRICING.get(model, DEFAULT_PRICING)
    input_cost = (input_tokens / 1_000_000.0) * rates["input"]
    output_cost = (output_tokens / 1_000_000.0) * rates["output"]
    return round(input_cost + output_cost, 7)


def log_and_record_claude_call(
    *,
    user_id: Optional[str],
    model: str,
    call_type: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    status: str,
    prompt: str,
    response: str,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    1. Writes formatted entry to `claude_chat.log` & structured entry to `claude_chat.jsonl`.
    2. Writes record and updates aggregate calculations in dedicated `token_usage.db`.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    total_tokens = input_tokens + output_tokens
    cost_usd = calculate_cost(model, input_tokens, output_tokens)
    uid_str = str(user_id) if user_id else "anonymous"

    # 1. Log to dedicated files
    try:
        text_logger, jsonl_logger = _setup_claude_loggers()

        # Detailed text log
        prompt_snippet = prompt.strip()
        response_snippet = response.strip()
        if len(prompt_snippet) > 1200:
            prompt_snippet = prompt_snippet[:1197] + "..."
        if len(response_snippet) > 1200:
            response_snippet = response_snippet[:1197] + "..."

        text_entry = (
            f"\n{'=' * 80}\n"
            f"[{now_utc}] CLAUDE INVOCATION | Model: {model} | Type: {call_type} | Status: {status}\n"
            f"User ID: {uid_str} | Latency: {duration_ms:.1f}ms | Cost: ${cost_usd:.6f}\n"
            f"Tokens: Input={input_tokens} | Output={output_tokens} | Total={total_tokens}\n"
            f"{'-' * 35} PROMPT {'-' * 35}\n"
            f"{prompt_snippet}\n"
            f"{'-' * 34} RESPONSE {'-' * 34}\n"
            f"{response_snippet}\n"
            f"{'=' * 80}"
        )
        text_logger.info(text_entry)

        # JSONL entry
        json_obj = {
            "timestamp": now_utc,
            "user_id": uid_str,
            "model": model,
            "call_type": call_type,
            "status": status,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "duration_ms": round(duration_ms, 2),
            "error_message": error_message,
            "prompt_length": len(prompt),
            "response_length": len(response),
        }
        jsonl_logger.info(json.dumps(json_obj))
    except Exception as exc:
        logger.warning("Failed to write to Claude log files: %s", exc)

    # 2. Record in dedicated SQLite database
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path, timeout=10.0) as conn:
            prompt_preview = (prompt[:300] + "...") if len(prompt) > 300 else prompt
            response_preview = (response[:300] + "...") if len(response) > 300 else response
            conn.execute(
                """
                INSERT INTO claude_token_records (
                    user_id, model, call_type, input_tokens, output_tokens,
                    total_tokens, cost_usd, duration_ms, status,
                    prompt_preview, response_preview, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    uid_str,
                    model,
                    call_type,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    cost_usd,
                    duration_ms,
                    status,
                    prompt_preview,
                    response_preview,
                    error_message,
                    now_utc,
                ),
            )

            # Update aggregated totals
            conn.execute(
                """
                INSERT INTO user_model_aggregates (
                    user_id, model, total_input_tokens, total_output_tokens,
                    total_tokens, total_cost_usd, request_count, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(user_id, model) DO UPDATE SET
                    total_input_tokens = total_input_tokens + excluded.total_input_tokens,
                    total_output_tokens = total_output_tokens + excluded.total_output_tokens,
                    total_tokens = total_tokens + excluded.total_tokens,
                    total_cost_usd = total_cost_usd + excluded.total_cost_usd,
                    request_count = request_count + 1,
                    last_used_at = excluded.last_used_at;
                """,
                (
                    uid_str,
                    model,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    cost_usd,
                    now_utc,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to record token usage in SQLite DB (%s): %s", db_path, exc)

    return {
        "user_id": uid_str,
        "model": model,
        "call_type": call_type,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "duration_ms": duration_ms,
        "status": status,
        "created_at": now_utc,
    }


def calculate_user_token_usage(user_id: str) -> Dict[str, Any]:
    """
    Calculate how many tokens are used for a specific user,
    with input and output tokens distinct, broken down by model.
    """
    db_path = _get_db_path()
    uid_str = str(user_id)

    total_in = 0
    total_out = 0
    total_all = 0
    total_cost = 0.0
    total_requests = 0
    by_model: List[Dict[str, Any]] = []

    try:
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    model,
                    total_input_tokens,
                    total_output_tokens,
                    total_tokens,
                    total_cost_usd,
                    request_count,
                    last_used_at
                FROM user_model_aggregates
                WHERE user_id = ?
                ORDER BY total_tokens DESC;
                """,
                (uid_str,),
            )
            rows = cursor.fetchall()

            for r in rows:
                m_in = int(r["total_input_tokens"] or 0)
                m_out = int(r["total_output_tokens"] or 0)
                m_tot = int(r["total_tokens"] or 0)
                m_cost = float(r["total_cost_usd"] or 0.0)
                m_req = int(r["request_count"] or 0)

                total_in += m_in
                total_out += m_out
                total_all += m_tot
                total_cost += m_cost
                total_requests += m_req

                by_model.append({
                    "model": r["model"],
                    "input_tokens": m_in,
                    "output_tokens": m_out,
                    "total_tokens": m_tot,
                    "cost_usd": round(m_cost, 6),
                    "cost_inr": round(m_cost * USD_TO_INR_RATE, 4),
                    "request_count": m_req,
                    "last_used_at": r["last_used_at"],
                })
    except Exception as exc:
        logger.warning("Error calculating user tokens from SQLite DB: %s", exc)

    return {
        "user_id": uid_str,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_all,
        "total_cost_usd": round(total_cost, 6),
        "total_cost_inr": round(total_cost * USD_TO_INR_RATE, 4),
        "total_requests": total_requests,
        "breakdown_by_model": by_model,
    }


def calculate_all_users_token_usage() -> List[Dict[str, Any]]:
    """
    Calculate token usage across all users, showing input vs output tokens distinct
    and what model is used.
    """
    db_path = _get_db_path()
    results: List[Dict[str, Any]] = []

    try:
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    user_id,
                    model,
                    total_input_tokens,
                    total_output_tokens,
                    total_tokens,
                    total_cost_usd,
                    request_count,
                    last_used_at
                FROM user_model_aggregates
                ORDER BY total_tokens DESC;
                """
            )
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "user_id": r["user_id"],
                    "model": r["model"],
                    "input_tokens": int(r["total_input_tokens"] or 0),
                    "output_tokens": int(r["total_output_tokens"] or 0),
                    "total_tokens": int(r["total_tokens"] or 0),
                    "cost_usd": round(float(r["total_cost_usd"] or 0.0), 6),
                    "request_count": int(r["request_count"] or 0),
                    "last_used_at": r["last_used_at"],
                })
    except Exception as exc:
        logger.warning("Error fetching all users token usage: %s", exc)

    return results


def get_recent_claude_records(limit: int = 50, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch recent individual Claude call records from dedicated database."""
    db_path = _get_db_path()
    records: List[Dict[str, Any]] = []
    try:
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    """
                    SELECT * FROM claude_token_records
                    WHERE user_id = ?
                    ORDER BY id DESC LIMIT ?;
                    """,
                    (str(user_id), limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM claude_token_records
                    ORDER BY id DESC LIMIT ?;
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            for r in rows:
                records.append(dict(r))
    except Exception as exc:
        logger.warning("Error reading recent Claude records: %s", exc)
    return records


async def call_claude_messages(
    messages: List[Dict[str, Any]],
    *,
    user_id: Optional[str] = None,
    call_type: str = "chat",
    model: Optional[str] = None,
    max_tokens: int = 500,
    temperature: float = 0.2,
    system_prompt: Optional[str] = None,
    timeout_sec: float = 30.0,
) -> Tuple[str, Dict[str, Any]]:
    """
    Central wrapper for all Claude invocations.
    Guarantees:
    1. Precise token tracking (input and output distinct).
    2. Detailed logging to `<FILE_LOG_DIR>/claude_chat.log` & `.jsonl`.
    3. Storage in dedicated SQLite metrics database `<FILE_LOG_DIR>/token_usage.db`.
    """
    api_key = (settings.ANTHROPIC_API_KEY or "").strip()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured.")

    chosen_model = model or settings.ANTHROPIC_MODEL or "claude-haiku-4-5-20251001"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": chosen_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system_prompt:
        payload["system"] = system_prompt

    # Format prompt preview for logging
    prompt_str = ""
    if system_prompt:
        prompt_str += f"[System: {system_prompt}]\n"
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            prompt_str += f"[{m.get('role', 'user')}]: {c}\n"
        elif isinstance(c, list):
            prompt_str += f"[{m.get('role', 'user')}]: (multi-part content: {len(c)} items)\n"

    t0 = time.perf_counter()
    status = "success"
    error_msg = None
    input_tokens = 0
    output_tokens = 0
    reply_text = ""

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            duration_ms = (time.perf_counter() - t0) * 1000.0

            if resp.status_code == 200:
                data = resp.json()
                content_list = data.get("content", [])
                text_parts = [c["text"] for c in content_list if c.get("type") == "text"]
                reply_text = "\n".join(text_parts).strip()

                usage = data.get("usage", {})
                input_tokens = int(usage.get("input_tokens", 0))
                output_tokens = int(usage.get("output_tokens", 0))
            else:
                status = f"http_{resp.status_code}"
                error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                reply_text = ""
                # Estimate prompt tokens if API call failed
                input_tokens = max(1, len(prompt_str) // 4)
                output_tokens = 0
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000.0
        status = "exception"
        error_msg = str(exc)
        input_tokens = max(1, len(prompt_str) // 4)
        output_tokens = 0
        reply_text = ""

    # Always log and record into dedicated database
    token_info = log_and_record_claude_call(
        user_id=user_id,
        model=chosen_model,
        call_type=call_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=duration_ms,
        status=status,
        prompt=prompt_str,
        response=reply_text,
        error_message=error_msg,
    )

    if status != "success" and error_msg:
        raise RuntimeError(f"Claude invocation failed ({status}): {error_msg}")

    return reply_text, token_info
