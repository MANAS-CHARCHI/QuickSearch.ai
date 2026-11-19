"""
Unit and Integration Tests for Claude API Token Tracking, Dedicated Log File & Token Metrics Database.
"""
import os
import sqlite3
import pytest
from app.services.claude_tracker import (
    calculate_cost,
    log_and_record_claude_call,
    calculate_user_token_usage,
    calculate_all_users_token_usage,
    get_recent_claude_records,
    _get_db_path,
)


def test_pricing_calculation():
    # Haiku 4.5: $0.25/M in, $1.25/M out
    # 1000 input tokens = $0.00025, 200 output tokens = $0.00025 -> total = $0.0005
    cost = calculate_cost("claude-haiku-4-5-20251001", 1000, 200)
    assert abs(cost - 0.0005) < 1e-6

    # Zero tokens = $0.0
    assert calculate_cost("claude-haiku-4-5-20251001", 0, 0) == 0.0


def test_token_logging_and_sqlite_database_recording():
    test_user_id = "test-user-uuid-999"
    model_name = "claude-haiku-4-5-20251001"

    # Call 1: 500 input, 150 output
    res1 = log_and_record_claude_call(
        user_id=test_user_id,
        model=model_name,
        call_type="test_document_summary",
        input_tokens=500,
        output_tokens=150,
        duration_ms=320.5,
        status="success",
        prompt="Analyze mutual fund holdings",
        response='{"document_type": "Mutual Fund"}',
    )
    assert res1["input_tokens"] == 500
    assert res1["output_tokens"] == 150
    assert res1["total_tokens"] == 650
    assert res1["status"] == "success"

    # Call 2: 300 input, 100 output
    res2 = log_and_record_claude_call(
        user_id=test_user_id,
        model=model_name,
        call_type="test_chat",
        input_tokens=300,
        output_tokens=100,
        duration_ms=210.0,
        status="success",
        prompt="What is the net asset value?",
        response="The net asset value is 92.57%.",
    )
    assert res2["total_tokens"] == 400

    # Test user calculations
    calc = calculate_user_token_usage(test_user_id)
    assert calc["user_id"] == test_user_id
    assert calc["total_input_tokens"] >= 800
    assert calc["total_output_tokens"] >= 250
    assert calc["total_tokens"] >= 1050
    assert calc["total_requests"] >= 2
    assert len(calc["breakdown_by_model"]) >= 1

    model_entry = next(m for m in calc["breakdown_by_model"] if m["model"] == model_name)
    assert model_entry["input_tokens"] >= 800
    assert model_entry["output_tokens"] >= 250
    assert model_entry["total_tokens"] >= 1050

    # Test all-users calculation
    all_users = calculate_all_users_token_usage()
    assert any(u["user_id"] == test_user_id for u in all_users)

    # Test recent records
    recent = get_recent_claude_records(limit=10, user_id=test_user_id)
    assert len(recent) >= 2
    assert recent[0]["user_id"] == test_user_id
    assert "prompt_preview" in recent[0]

    # Verify dedicated log files exist and are populated
    from app.core.config import settings
    log_dir = settings.FILE_LOG_DIR or "/app/logs"
    text_log = os.path.join(log_dir, "claude_chat.log")
    jsonl_log = os.path.join(log_dir, "claude_chat.jsonl")
    db_path = _get_db_path()

    assert os.path.exists(text_log) and os.path.getsize(text_log) > 0
    assert os.path.exists(jsonl_log) and os.path.getsize(jsonl_log) > 0
    assert os.path.exists(db_path) and os.path.getsize(db_path) > 0
