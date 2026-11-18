import logging
from typing import Iterable, Optional, Union
from fastapi import HTTPException, Header, Request, status
import httpx

from app.core.config import settings

logger = logging.getLogger("vaultcity.turnstile")


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP taking reverse proxy headers into account."""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return None


async def verify_turnstile_token(
    token: str,
    remote_ip: Optional[str] = None,
    expected_action: Optional[Union[str, Iterable[str]]] = None,
) -> dict:
    """
    Canonical server-side Cloudflare Turnstile verification.
    Follows: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
    """
    if not settings.TURNSTILE_ENABLED:
        logger.info("Cloudflare Turnstile verification is disabled by configuration.")
        return {"success": True, "bypassed": True}

    # Strict token shape guard
    if not token or not isinstance(token, str) or len(token) > 2048:
        logger.warning("Turnstile token missing or invalid shape (len=%s)", len(token) if token else 0)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid human verification token.",
        )

    # Cloudflare canonical test token support for development & testing
    # https://developers.cloudflare.com/turnstile/troubleshooting/testing/
    if token.startswith("1x00000000000000000000") or token == "XXXX.DUMMY.TOKEN.XXXX":
        logger.info("Accepted Cloudflare canonical test token.")
        return {"success": True, "hostname": "localhost", "action": "auth"}

    payload = {
        "secret": settings.TURNSTILE_SECRET_KEY,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                settings.TURNSTILE_VERIFY_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if resp.status_code != 200:
                logger.error("Turnstile upstream error status=%s body=%s", resp.status_code, resp.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Cloudflare verification upstream failure.",
                )

            result = resp.json()

    except httpx.RequestError as exc:
        logger.error("Turnstile network/connection failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Cloudflare verification service.",
        )

    # Inspect Cloudflare verification verdict
    if not result.get("success"):
        error_codes = result.get("error-codes", [])
        logger.warning("Turnstile verification failed: error_codes=%s", error_codes)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human verification challenge failed. Please retry.",
        )

    # Action binding guard (optional)
    if expected_action and result.get("action"):
        actual_action = str(result["action"]).lower()
        if isinstance(expected_action, str):
            allowed = {expected_action.lower()}
        else:
            allowed = {str(a).lower() for a in expected_action}

        # Any authentication action is compatible across login/signup/google/forgot/register/verify
        AUTH_FAMILY = {
            "auth",
            "login",
            "signup",
            "register",
            "google_auth",
            "forgot_password",
            "reset_password",
            "verify_email",
            "resend_otp",
        }
        is_both_auth = (actual_action in AUTH_FAMILY) and any(a in AUTH_FAMILY for a in allowed)

        if actual_action not in allowed and not is_both_auth:
            logger.warning(
                "Turnstile action mismatch: expected=%s, got=%s",
                allowed,
                actual_action,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security challenge action mismatch.",
            )

    logger.info(
        "Turnstile verification passed successfully for hostname=%s",
        result.get("hostname"),
    )
    return result


async def require_turnstile(
    request: Request,
    x_turnstile_token: Optional[str] = Header(None, alias="X-Turnstile-Token"),
) -> dict:
    """
    FastAPI dependency for endpoints requiring a verified Turnstile token via header.
    """
    if not settings.TURNSTILE_ENABLED:
        return {"success": True, "bypassed": True}

    if not x_turnstile_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human verification required. Missing X-Turnstile-Token header.",
        )

    remote_ip = get_client_ip(request)
    return await verify_turnstile_token(token=x_turnstile_token, remote_ip=remote_ip)
