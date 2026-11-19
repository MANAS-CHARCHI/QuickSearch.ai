"""
Token Usage & Metrics API.

Calculates and serves exact token usage metrics from the dedicated SQLite database:
- Separate input tokens and output tokens per user.
- Breakdown by model used.
- Cost calculations in USD.
- Audit records from claude_token_records.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from app.api.v1.auth import get_current_user
from app.core.redis import (
    get_json_cache,
    set_json_cache,
    make_user_tokens_cache_key,
)
from app.models.user import User
from app.services.claude_tracker import (
    calculate_all_users_token_usage,
    calculate_user_token_usage,
    get_recent_claude_records,
)

logger = logging.getLogger("vaultcity.tokens")

router = APIRouter(prefix="/tokens", tags=["Token Usage & Calculations"])


@router.get("/my-usage")
async def get_my_token_usage(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Calculate token usage for the currently authenticated user.
    Served with high-speed Redis caching (<1ms response).
    """
    uid_str = str(current_user.id)
    cache_key = make_user_tokens_cache_key(uid_str)
    cached = await get_json_cache(cache_key)
    if cached is not None:
        return cached

    usage = calculate_user_token_usage(uid_str)
    await set_json_cache(cache_key, usage, ttl_seconds=300)
    return usage


@router.get("/summary")
async def get_all_users_token_summary(
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Calculate token usage across all users, showing:
    - user_id
    - model
    - input_tokens
    - output_tokens
    - total_tokens
    - cost_usd
    - request_count
    - last_used_at
    """
    return calculate_all_users_token_usage()


@router.get("/records")
async def get_my_recent_token_records(
    limit: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Fetch recent individual Claude call records for the current user."""
    return get_recent_claude_records(limit=limit, user_id=str(current_user.id))
