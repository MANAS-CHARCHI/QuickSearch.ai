"""
Async SMTP Email Service for Vault City AI.
Supports Gmail SMTP (smtp.gmail.com:587 STARTTLS with App Password) and any standard SMTP server.
Provides:
  1. 6-digit Email Verification OTP emails during user onboarding
  2. Password Reset link & token emails for account recovery
  3. Graceful console-log fallback in local development when SMTP credentials are unset
"""
from __future__ import annotations

import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import html
import logging
import smtplib
import ssl
from typing import Any, Dict
from urllib.parse import urlencode

from app.core.config import settings

logger = logging.getLogger("vaultcity.email")


def is_smtp_configured() -> bool:
    """Return True when SMTP delivery is enabled and credentials are present."""
    return bool(
        settings.SMTP_ENABLED
        and settings.SMTP_HOST
        and settings.SMTP_USERNAME
        and settings.SMTP_PASSWORD
    )


def _send_smtp_sync(
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: str,
) -> None:
    """Synchronous SMTP dispatch executed inside a worker thread."""
    from_email = (settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME or "").strip()
    username = (settings.SMTP_USERNAME or "").strip()
    # Gmail App Passwords are often copied with spaces (e.g. "abcd efgh ijkl mnop")
    password = (settings.SMTP_PASSWORD or "").replace(" ", "").strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, from_email))
    msg["To"] = to_email

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if settings.SMTP_VERIFY_SSL:
        context = ssl.create_default_context(cafile=settings.SMTP_CA_BUNDLE or None)
    else:
        logger.warning("SMTP_VERIFY_SSL=False: TLS certificate verification disabled (use only in local dev).")
        context = ssl._create_unverified_context()

    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=15,
            context=context,
        ) as server:
            server.login(username, password)
            server.sendmail(from_email, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=15,
        ) as server:
            server.ehlo()
            if settings.SMTP_USE_TLS:
                server.starttls(context=context)
                server.ehlo()
            server.login(username, password)
            server.sendmail(from_email, [to_email], msg.as_string())


async def send_email(
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: str,
) -> Dict[str, Any]:
    """
    Send an email asynchronously via configured SMTP server with automatic retries
    for transient network/socket drops, or log to console in dev when credentials are unset.
    """
    if not is_smtp_configured():
        logger.warning(
            "[SMTP FALLBACK - NO CREDENTIALS SET] To=%s | Subject=%s\n%s",
            to_email,
            subject,
            plain_body,
        )
        return {"delivered": False, "mode": "console_fallback"}

    max_attempts = max(1, settings.SMTP_MAX_RETRIES + 1)
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            await asyncio.to_thread(_send_smtp_sync, to_email, subject, plain_body, html_body)
            logger.info(
                "SMTP email sent successfully to=%s subject=%s (attempt=%d/%d)",
                to_email,
                subject,
                attempt,
                max_attempts,
            )
            return {"delivered": True, "mode": "smtp", "attempts": attempt}
        except smtplib.SMTPAuthenticationError as exc:
            # Never retry bad credentials
            logger.error("SMTP authentication failed for to=%s: %s", to_email, exc)
            raise RuntimeError(f"SMTP authentication failed — verify SMTP_USERNAME and App Password: {exc}") from exc
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, TimeoutError, OSError) as exc:
            last_exc = exc
            logger.warning(
                "Transient SMTP error for to=%s (attempt %d/%d): %s",
                to_email,
                attempt,
                max_attempts,
                exc,
            )
            if attempt < max_attempts:
                await asyncio.sleep(0.8 * attempt)
        except Exception as exc:
            logger.error("SMTP delivery failed for to=%s: %s", to_email, exc)
            raise RuntimeError(f"Failed to send email via SMTP: {exc}") from exc

    logger.error("SMTP delivery failed after %d attempts for to=%s: %s", max_attempts, to_email, last_exc)
    raise RuntimeError(f"Failed to send email via SMTP after {max_attempts} attempts: {last_exc}") from last_exc


async def send_verification_otp_email(
    to_email: str,
    username: str,
    otp_code: str,
    expire_minutes: int | None = None,
) -> Dict[str, Any]:
    """Send 6-digit onboarding verification OTP email."""
    ttl_min = expire_minutes or settings.OTP_EXPIRE_MINUTES
    safe_user = html.escape(username or to_email.split("@")[0])
    safe_otp = html.escape(otp_code)
    spaced_otp = " ".join(list(safe_otp))

    subject = f"{otp_code} is your Vault City verification code"

    plain_body = (
        f"Hi {username or to_email.split('@')[0]},\n\n"
        f"Welcome to Vault City AI! Use the 6-digit verification code below to verify your email and activate your account:\n\n"
        f"    {otp_code}\n\n"
        f"This code expires in {ttl_min} minutes.\n"
        f"If you did not create a Vault City account, you can safely ignore this email.\n\n"
        f"— Vault City Security"
    )

    html_body = f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background-color:#FFFCF9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1c1917;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:480px;background-color:#ffffff;border:1px solid #fed7aa;border-radius:16px;padding:32px;">
            <tr>
              <td style="padding-bottom:20px;border-bottom:1px solid #ffedd5;">
                <span style="font-size:18px;font-weight:800;letter-spacing:-0.02em;color:#0c0a09;">vault city</span>
                <span style="font-family:monospace;font-size:12px;color:#a8a29e;margin-left:6px;">/ onboarding</span>
              </td>
            </tr>
            <tr>
              <td style="padding-top:24px;">
                <h1 style="margin:0 0 8px 0;font-size:20px;font-weight:700;color:#1c1917;">Verify your email address</h1>
                <p style="margin:0 0 20px 0;font-size:14px;line-height:1.6;color:#57534e;">
                  Hi <strong>{safe_user}</strong>, enter the 6-digit verification code below in Vault City to activate your encrypted account:
                </p>
                <div style="background-color:#fff7ed;border:1px dashed #fb923c;border-radius:12px;padding:20px;text-align:center;margin:20px 0;">
                  <span style="font-family:'Courier New',Courier,monospace;font-size:32px;font-weight:800;letter-spacing:0.22em;color:#ea580c;">{spaced_otp}</span>
                </div>
                <p style="margin:0 0 8px 0;font-size:12px;color:#78716c;">
                  This verification code expires in <strong>{ttl_min} minutes</strong> and can only be used once.
                </p>
                <p style="margin:0;font-size:12px;color:#a8a29e;">
                  If you didn't request this code, you can safely ignore this email.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding-top:24px;margin-top:24px;border-top:1px solid #f5f5f4;font-family:monospace;font-size:11px;color:#a8a29e;">
                Vault City AI • Zero-Knowledge Personal Cloud
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return await send_email(to_email, subject, plain_body, html_body)


async def send_password_reset_email(
    to_email: str,
    username: str,
    reset_token: str,
) -> Dict[str, Any]:
    """Send password recovery link + token email via SMTP."""
    safe_user = html.escape(username or to_email.split("@")[0])
    frontend_base = settings.FRONTEND_URL.rstrip("/")
    query = urlencode({"mode": "reset_password", "token": reset_token})
    reset_url = f"{frontend_base}/?{query}"
    safe_url = html.escape(reset_url, quote=True)
    safe_token = html.escape(reset_token)

    subject = "Reset your Vault City master password"

    plain_body = (
        f"Hi {username or to_email.split('@')[0]},\n\n"
        f"We received a request to reset your Vault City master password.\n\n"
        f"Reset Link (valid for 1 hour):\n"
        f"{reset_url}\n\n"
        f"Or paste this recovery token directly in the app:\n"
        f"{reset_token}\n\n"
        f"If you did not request a password reset, you can safely ignore this email.\n\n"
        f"— Vault City Security"
    )

    html_body = f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background-color:#FFFCF9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1c1917;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:500px;background-color:#ffffff;border:1px solid #fed7aa;border-radius:16px;padding:32px;">
            <tr>
              <td style="padding-bottom:20px;border-bottom:1px solid #ffedd5;">
                <span style="font-size:18px;font-weight:800;letter-spacing:-0.02em;color:#0c0a09;">vault city</span>
                <span style="font-family:monospace;font-size:12px;color:#a8a29e;margin-left:6px;">/ recovery</span>
              </td>
            </tr>
            <tr>
              <td style="padding-top:24px;">
                <h1 style="margin:0 0 8px 0;font-size:20px;font-weight:700;color:#1c1917;">Reset your master password</h1>
                <p style="margin:0 0 20px 0;font-size:14px;line-height:1.6;color:#57534e;">
                  Hi <strong>{safe_user}</strong>, click the button below to choose a new master password for your Vault City account:
                </p>
                <div style="text-align:center;margin:24px 0;">
                  <a href="{safe_url}" style="display:inline-block;background-color:#ea580c;color:#ffffff;text-decoration:none;font-weight:600;font-size:14px;padding:12px 24px;border-radius:10px;">
                    Reset Master Password
                  </a>
                </div>
                <p style="margin:0 0 8px 0;font-size:12px;color:#78716c;">
                  Or copy and paste this recovery token into Vault City (expires in <strong>1 hour</strong>):
                </p>
                <div style="background-color:#fafaf9;border:1px solid #e7e5e4;border-radius:8px;padding:10px 12px;font-family:monospace;font-size:11px;word-break:break-all;color:#44403c;margin-bottom:16px;">
                  {safe_token}
                </div>
                <p style="margin:0;font-size:12px;color:#a8a29e;">
                  If you didn't request this reset, no changes have been made to your account.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding-top:24px;border-top:1px solid #f5f5f4;font-family:monospace;font-size:11px;color:#a8a29e;">
                Vault City AI • Zero-Knowledge Personal Cloud
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return await send_email(to_email, subject, plain_body, html_body)
