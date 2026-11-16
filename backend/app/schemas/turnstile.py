"""
Cloudflare Turnstile schemas for bot protection and human verification.
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TurnstileVerifyRequest(BaseModel):
    """Payload to verify Turnstile token against Cloudflare."""
    model_config = ConfigDict(extra="ignore")

    token: str = Field(..., min_length=1, max_length=2048, description="Cloudflare Turnstile response token")
    action: Optional[str] = Field(None, max_length=64, description="Action bound to the challenge")


class TurnstileVerifyResponse(BaseModel):
    """Cloudflare verification verdict response."""
    model_config = ConfigDict(from_attributes=True)

    success: bool
    status: str
    hostname: Optional[str] = None
    action: Optional[str] = None
    challenge_ts: Optional[str] = None
