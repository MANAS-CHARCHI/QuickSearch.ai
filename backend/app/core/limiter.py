import logging
from typing import Any, Callable, Optional
from fastapi import HTTPException, Request, Response, status
from pylimitx import RateLimitExceeded, RateLimiter
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger("vaultcity.limiter")


class SlidingWindowRateLimiter:
    """
    Thin FastAPI adapter over pylimitx.RateLimiter (Redis + Lua + CircuitBreaker).
    Safe for multi-instance deployments with Cloudflare / reverse-proxy IP extraction.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        fail_open: Optional[bool] = None,
        failure_threshold: int = 3,
        recovery_timeout: int = 30,
        cleanup_interval_seconds: int = 300,  # kept for backwards compatibility
    ):
        self._custom_redis = redis_client
        self._fail_open = settings.RATE_LIMIT_FAIL_OPEN if fail_open is None else fail_open
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._engine: Optional[RateLimiter] = None

    def _get_engine(self) -> RateLimiter:
        """Lazily initialize pylimitx RateLimiter inside the active event loop."""
        if self._engine is None:
            redis_client = self._custom_redis or Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
            )
            self._engine = RateLimiter(
                redis=redis_client,
                fail_open=self._fail_open,
                failure_threshold=self._failure_threshold,
                recovery_timeout=self._recovery_timeout,
            )
        return self._engine

    @staticmethod
    def _extract_client_ip(request: Request) -> str:
        """Extract true client IP supporting Cloudflare and reverse proxies."""
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()

        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        if request.client and request.client.host:
            return request.client.host

        return "unknown-client"

    async def check(
        self,
        request: Request,
        response: Response,
        max_requests: int,
        window_seconds: int,
        key_prefix: str = "global",
        algorithm: str = "sliding_window",
    ) -> None:
        """Check distributed Redis rate limit via pylimitx. Raises HTTP 429 if exceeded."""
        client_ip = self._extract_client_ip(request)
        engine = self._get_engine()

        try:
            result = await engine.check(
                namespace=key_prefix,
                identifier=client_ip,
                limit=max_requests,
                window=window_seconds,
                algorithm=algorithm,
            )
        except RateLimitExceeded as exc:
            retry_after = max(1, int(exc.retry_after))
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["Retry-After"] = str(retry_after)
            logger.warning(
                "Rate limit exceeded for %s:%s (limit=%s/%ss, retry in %ss)",
                key_prefix,
                client_ip,
                max_requests,
                window_seconds,
                retry_after,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Rate limit exceeded. Please wait {retry_after} seconds before trying again.",
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(retry_after),
                },
            ) from exc

        if result.remaining >= 0:
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(result.remaining)


# Global distributed limiter instance (backed by pylimitx + Redis)
limiter = SlidingWindowRateLimiter()


def rate_limit(
    max_requests: int = 60,
    window_seconds: int = 60,
    key_prefix: str = "endpoint",
    algorithm: str = "sliding_window",
) -> Callable:
    """
    FastAPI dependency factory for distributed Redis rate limiting via pylimitx.

    Usage:
    @router.post("/login", dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, key_prefix="auth_login"))])
    """
    async def dependency(request: Request, response: Response):
        await limiter.check(
            request=request,
            response=response,
            max_requests=max_requests,
            window_seconds=window_seconds,
            key_prefix=key_prefix,
            algorithm=algorithm,
        )

    return dependency
