"""
Redis Token & Session Management using Hash Maps for minimal latency O(1) lookups.
Stores exp and jti mapping for access (15 min) and refresh (7 days) tokens.
Includes thread-safe async client with fallback memory map for offline test execution.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

from app.core.config import settings

logger = logging.getLogger("vaultcity.redis")

# Global Redis connection pool
_redis_client: Optional[Any] = None
_redis_available: bool = True if aioredis is not None else False

# In-memory fallback map (jti -> dict, and user_id -> dict) when Redis server is offline
_memory_token_map: Dict[str, Dict[str, Any]] = {}
_memory_user_tokens: Dict[str, Dict[str, str]] = {}


async def get_redis_client() -> Optional[Any]:
    """Retrieve or initialize singleton Redis async connection pool."""
    global _redis_client, _redis_available
    if aioredis is None:
        return None

    if _redis_client is not None:
        return _redis_client

    if not _redis_available:
        return None
        return None

    try:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
        # Verify connection
        await _redis_client.ping()
        logger.info("Connected to Redis cache at %s", settings.REDIS_URL)
        return _redis_client
    except Exception as e:
        logger.warning(
            "Redis connection failed (%s); operating with in-memory token map fallback.", e
        )
        _redis_available = False
        _redis_client = None
        return None


async def store_token_mapping(
    jti: str,
    user_id: str,
    token_type: str,
    exp_timestamp: int,
) -> bool:
    """
    Store token exp and jti mapping in Redis Hash Map for minimal O(1) response time.
    1. HSET vault:token:{jti} mapping with jti, sub, type, exp, revoked
    2. EXPIRE vault:token:{jti} set to token TTL
    3. HSET vault:user_tokens:{user_id} mapping jti -> exp
    """
    now = int(time.time())
    ttl = max(1, exp_timestamp - now)
    user_id_str = str(user_id)

    # In-memory fallback store
    _memory_token_map[jti] = {
        "jti": jti,
        "sub": user_id_str,
        "type": token_type,
        "exp": exp_timestamp,
        "created_at": now,
        "revoked": 0,
    }
    if user_id_str not in _memory_user_tokens:
        _memory_user_tokens[user_id_str] = {}
    _memory_user_tokens[user_id_str][jti] = str(exp_timestamp)

    client = await get_redis_client()
    if not client:
        return True

    try:
        token_key = f"vault:token:{jti}"
        user_key = f"vault:user_tokens:{user_id_str}"

        # Pipeline atomic execution for minimal latency (< 1ms)
        async with client.pipeline(transaction=True) as pipe:
            pipe.hset(
                token_key,
                mapping={
                    "jti": jti,
                    "sub": user_id_str,
                    "type": token_type,
                    "exp": str(exp_timestamp),
                    "created_at": str(now),
                    "revoked": "0",
                },
            )
            pipe.expire(token_key, ttl)
            pipe.hset(user_key, jti, f"{token_type}:{exp_timestamp}")
            # Keep user token map alive for 8 days (covers 7-day refresh lifecycle)
            pipe.expire(user_key, 60 * 60 * 24 * 8)
            await pipe.execute()
        return True
    except Exception as e:
        logger.error("Redis store_token_mapping failure for jti=%s: %s", jti, e)
        return True  # Fallback memory map is populated


async def is_token_valid(jti: str, user_id: Optional[str] = None) -> bool:
    """
    Check if token jti exists in Redis Hash Map and is NOT revoked.
    Runs in minimal O(1) time.
    """
    now = int(time.time())

    # Check in-memory fallback first if present
    mem_token = _memory_token_map.get(jti)
    if mem_token:
        if mem_token.get("revoked") == 1:
            return False
        if mem_token.get("exp", 0) < now:
            return False

    client = await get_redis_client()
    if not client:
        return mem_token is not None and mem_token.get("revoked") == 0

    try:
        token_key = f"vault:token:{jti}"
        token_data = await client.hgetall(token_key)
        if not token_data:
            # If not in Redis and not in memory fallback, consider invalid
            return mem_token is not None and mem_token.get("revoked") == 0

        # Check revoked flag
        if token_data.get("revoked") == "1":
            return False

        # Check expiration timestamp
        exp = int(token_data.get("exp", 0))
        if exp < now:
            return False

        # Optional user match guard
        if user_id and token_data.get("sub") != str(user_id):
            return False

        return True
    except Exception as e:
        logger.warning("Redis is_token_valid check failed for jti=%s: %s", jti, e)
        return mem_token is not None and mem_token.get("revoked") == 0


async def revoke_token(jti: str, user_id: Optional[str] = None) -> bool:
    """
    Revoke a single token by JTI in Redis map and memory fallback.
    Minimal O(1) hash map update.
    """
    if jti in _memory_token_map:
        _memory_token_map[jti]["revoked"] = 1

    if user_id and str(user_id) in _memory_user_tokens:
        _memory_user_tokens[str(user_id)].pop(jti, None)

    client = await get_redis_client()
    if not client:
        return True

    try:
        token_key = f"vault:token:{jti}"
        async with client.pipeline(transaction=True) as pipe:
            pipe.hset(token_key, "revoked", "1")
            # Set short TTL so revoked record cleans up automatically
            pipe.expire(token_key, 60 * 60 * 24 * 7)
            if user_id:
                pipe.hdel(f"vault:user_tokens:{user_id}", jti)
            await pipe.execute()
        return True
    except Exception as e:
        logger.error("Redis revoke_token failure for jti=%s: %s", jti, e)
        return False


async def revoke_all_user_tokens(user_id: str) -> bool:
    """
    Revoke all active tokens for a specific user (e.g. password reset or account lock).
    """
    user_id_str = str(user_id)
    if user_id_str in _memory_user_tokens:
        for jti in list(_memory_user_tokens[user_id_str].keys()):
            if jti in _memory_token_map:
                _memory_token_map[jti]["revoked"] = 1
        _memory_user_tokens.pop(user_id_str, None)

    client = await get_redis_client()
    if not client:
        return True

    try:
        user_key = f"vault:user_tokens:{user_id_str}"
        jtis = await client.hkeys(user_key)
        if jtis:
            async with client.pipeline(transaction=True) as pipe:
                for jti in jtis:
                    pipe.hset(f"vault:token:{jti}", "revoked", "1")
                    pipe.expire(f"vault:token:{jti}", 3600)
                pipe.delete(user_key)
                await pipe.execute()
        return True
    except Exception as e:
        logger.error("Redis revoke_all_user_tokens failure for user=%s: %s", user_id_str, e)
        return False


async def get_token_metadata(jti: str) -> Optional[Dict[str, Any]]:
    """Retrieve token details from Redis map or memory fallback."""
    if jti in _memory_token_map:
        return _memory_token_map[jti]

    client = await get_redis_client()
    if not client:
        return None

    try:
        return await client.hgetall(f"vault:token:{jti}")
    except Exception as e:
        logger.warning("Redis get_token_metadata failure for jti=%s: %s", jti, e)
        return None
