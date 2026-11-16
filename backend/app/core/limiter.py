import asyncio
import logging
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional
from fastapi import HTTPException, Request, Response, status

logger = logging.getLogger("vaultcity.limiter")


class SlidingWindowRateLimiter:
    """
    Sliding window in-memory rate limiter with thread-safe lock and periodic memory cleanup.
    Tracks timestamps per key (IP address or authenticated user).
    """

    def __init__(self, cleanup_interval_seconds: int = 300):
        # key -> list of float timestamps
        self._records: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval_seconds

    def _extract_client_ip(self, request: Request) -> str:
        """Extract true client IP supporting Cloudflare and reverse proxies."""
        # 1. Cloudflare CF-Connecting-IP
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()

        # 2. Standard X-Forwarded-For header
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Client IP is the first IP in the comma-separated chain
            return forwarded.split(",")[0].strip()

        # 3. Direct client host
        if request.client and request.client.host:
            return request.client.host

        return "unknown-client"

    def _cleanup_old_records(self, now: float, max_window: float = 3600.0):
        """Remove keys whose timestamps are all older than max_window."""
        stale_keys = []
        for key, timestamps in self._records.items():
            valid_ts = [ts for ts in timestamps if (now - ts) <= max_window]
            if not valid_ts:
                stale_keys.append(key)
            else:
                self._records[key] = valid_ts
        for k in stale_keys:
            del self._records[k]
        self._last_cleanup = now

    async def check(
        self,
        request: Request,
        response: Response,
        max_requests: int,
        window_seconds: int,
        key_prefix: str = "global",
    ) -> None:
        """
        Check rate limit. Raises HTTPException(429) if exceeded.
        Appends rate limit headers to the response.
        """
        client_ip = self._extract_client_ip(request)
        rate_key = f"{key_prefix}:{client_ip}"
        now = time.time()
        window_start = now - window_seconds

        async with self._lock:
            # Periodic cleanup
            if (now - self._last_cleanup) > self._cleanup_interval:
                self._cleanup_old_records(now)

            # Filter out entries outside current window
            timestamps = self._records[rate_key]
            active_timestamps = [ts for ts in timestamps if ts > window_start]
            self._records[rate_key] = active_timestamps

            count = len(active_timestamps)

            # Calculate remaining (after current request) and reset
            remaining = max(0, max_requests - (count + 1))
            oldest_active = active_timestamps[0] if active_timestamps else now
            reset_seconds = max(1, int(window_seconds - (now - oldest_active)))

            # Set response headers
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_seconds)

            if count >= max_requests:
                response.headers["Retry-After"] = str(reset_seconds)
                logger.warning(
                    "Rate limit exceeded for key=%s (count=%s/%s in %ss, retry in %ss)",
                    rate_key,
                    count,
                    max_requests,
                    window_seconds,
                    reset_seconds,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Rate limit exceeded. Please wait {reset_seconds} seconds before trying again.",
                    headers={"Retry-After": str(reset_seconds)},
                )

            # Record this valid request timestamp
            self._records[rate_key].append(now)


# Global limiter instance
limiter = SlidingWindowRateLimiter()


def rate_limit(
    max_requests: int = 60,
    window_seconds: int = 60,
    key_prefix: str = "endpoint",
) -> Callable:
    """
    FastAPI dependency factory for rate limiting routes.
    
    Usage:
    @router.post("/login", dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, key_prefix="login"))])
    """
    async def dependency(request: Request, response: Response):
        await limiter.check(
            request=request,
            response=response,
            max_requests=max_requests,
            window_seconds=window_seconds,
            key_prefix=key_prefix,
        )

    return dependency
