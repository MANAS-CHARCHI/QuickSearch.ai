"""
Redis Refresh Token Cache & Session Management.
Focuses strictly on long-lived Refresh Tokens (7 days) with explicit TTLs.
Access tokens (5 min) are purely stateless JWTs verified via HS256 signature in memory.
Implements Cache-Aside:
- If refresh token is in Redis and valid -> fast O(1) response.
- If refresh token is removed/evicted from Redis -> falls back to PostgreSQL as source of truth.
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
    """Retrieve or initialize singleton Redis async connection pool with tight timeouts."""
    global _redis_client, _redis_available
    if aioredis is None:
        return None

    if _redis_client is not None:
        return _redis_client

    if not _redis_available:
        return None

    try:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=1.5,
            socket_connect_timeout=1.5,
        )
        # Fast ping verification
        await _redis_client.ping()
        logger.info("Connected to Redis cache at %s", settings.REDIS_URL)
        return _redis_client
    except Exception as e:
        logger.warning(
            "Redis connection failed (%s); operating with in-memory fallback.", e
        )
        _redis_available = False
        _redis_client = None
        return None


async def store_refresh_token(
    jti: str,
    user_id: str,
    exp_timestamp: int,
    raw_token: Optional[str] = None,
) -> bool:
    """
    Store refresh token in Redis with exact TTL (7 days).
    Enforces strict TTL on every key:
    - vault:refresh:{jti} with TTL = exp_timestamp - now
    - vault:user_refresh_tokens:{user_id} set with TTL
    """
    now = int(time.time())
    ttl = max(1, exp_timestamp - now)
    user_id_str = str(user_id)

    # In-memory fallback store
    _memory_token_map[jti] = {
        "jti": jti,
        "sub": user_id_str,
        "type": "refresh",
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
        refresh_key = f"vault:refresh:{jti}"
        user_key = f"vault:user_refresh_tokens:{user_id_str}"

        async with client.pipeline(transaction=True) as pipe:
            mapping_data = {
                "jti": jti,
                "sub": user_id_str,
                "exp": str(exp_timestamp),
                "created_at": str(now),
                "revoked": "0",
            }
            if raw_token:
                mapping_data["token_prefix"] = raw_token[:16]

            pipe.hset(refresh_key, mapping=mapping_data)
            pipe.expire(refresh_key, ttl)

            pipe.sadd(user_key, jti)
            # Keep user set alive for token duration + 1 hour
            pipe.expire(user_key, max(ttl + 3600, 60 * 60 * 24 * 8))
            await pipe.execute()
        return True
    except Exception as e:
        logger.error("Redis store_refresh_token failure for jti=%s: %s", jti, e)
        return True


async def check_refresh_token_in_redis(
    jti: str,
    user_id: Optional[str] = None,
) -> Optional[bool]:
    """
    Check refresh token status in Redis cache in O(1) time.
    Returns:
      True:  Found in Redis and valid (not revoked and not expired).
      False: Found in Redis but revoked or expired.
      None:  Cache miss (removed, evicted from Redis, or Redis offline) -> check Database!
    """
    now = int(time.time())

    # Check in-memory fallback first
    if jti in _memory_token_map:
        mem = _memory_token_map[jti]
        if mem.get("revoked") == 1:
            return False
        if mem.get("exp", 0) < now:
            return False
        if user_id and mem.get("sub") != str(user_id):
            return False
        return True

    client = await get_redis_client()
    if not client:
        # Cache miss (Redis offline) -> delegate to Database as source of truth
        return None

    try:
        refresh_key = f"vault:refresh:{jti}"
        data = await client.hgetall(refresh_key)
        if not data:
            # Token not in Redis (evicted / expired / removed) -> Cache miss!
            return None

        # Check revoked flag
        if data.get("revoked") == "1":
            return False

        # Check expiration
        exp = int(data.get("exp", 0))
        if exp < now:
            return False

        # Optional user match guard
        if user_id and data.get("sub") != str(user_id):
            return False

        return True
    except Exception as e:
        logger.warning("Redis check_refresh_token_in_redis error for jti=%s: %s", jti, e)
        return None


async def revoke_refresh_token(jti: str, user_id: Optional[str] = None) -> bool:
    """
    Revoke a single refresh token in Redis map with 3600s tombstone TTL.
    """
    if jti in _memory_token_map:
        _memory_token_map[jti]["revoked"] = 1

    if user_id and str(user_id) in _memory_user_tokens:
        _memory_user_tokens[str(user_id)].pop(jti, None)

    client = await get_redis_client()
    if not client:
        return True

    try:
        refresh_key = f"vault:refresh:{jti}"
        async with client.pipeline(transaction=True) as pipe:
            pipe.hset(refresh_key, "revoked", "1")
            pipe.expire(refresh_key, 3600)  # 1 hour tombstone TTL
            if user_id:
                pipe.srem(f"vault:user_refresh_tokens:{user_id}", jti)
            await pipe.execute()
        return True
    except Exception as e:
        logger.error("Redis revoke_refresh_token failure for jti=%s: %s", jti, e)
        return False


async def revoke_all_user_refresh_tokens(user_id: str) -> bool:
    """
    Revoke all active refresh tokens for a specific user (password reset / account lock).
    Ensures tombstones have strict 3600-second TTLs.
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
        user_key = f"vault:user_refresh_tokens:{user_id_str}"
        jtis = await client.smembers(user_key)
        if jtis:
            async with client.pipeline(transaction=True) as pipe:
                for jti in jtis:
                    pipe.hset(f"vault:refresh:{jti}", "revoked", "1")
                    pipe.expire(f"vault:refresh:{jti}", 3600)
                pipe.delete(user_key)
                await pipe.execute()
        return True
    except Exception as e:
        logger.error("Redis revoke_all_user_refresh_tokens failure for user=%s: %s", user_id_str, e)
        return False


async def get_refresh_token_metadata(jti: str) -> Optional[Dict[str, Any]]:
    """Retrieve refresh token details from Redis map or memory fallback."""
    if jti in _memory_token_map:
        return _memory_token_map[jti]

    client = await get_redis_client()
    if not client:
        return None

    try:
        return await client.hgetall(f"vault:refresh:{jti}")
    except Exception as e:
        logger.warning("Redis get_refresh_token_metadata failure for jti=%s: %s", jti, e)
        return None


# Backward compatibility aliases
store_token_mapping = store_refresh_token
store_refresh_token_in_redis = store_refresh_token
is_token_valid = check_refresh_token_in_redis
revoke_token = revoke_refresh_token
revoke_all_user_tokens = revoke_all_user_refresh_tokens
get_token_metadata = get_refresh_token_metadata
