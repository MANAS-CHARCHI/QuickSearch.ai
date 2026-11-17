"""
Authentication schemas for registration, login, OAuth2, and password recovery.
"""
from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.user import UserResponse


class UserRegisterRequest(BaseModel):
    """Request payload to register a new user with password and Turnstile token."""
    model_config = ConfigDict(extra="ignore")

    email: str = Field(..., min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="Valid email address")
    username: Optional[str] = Field(None, min_length=2, max_length=100, description="Display username")
    password: str = Field(..., min_length=8, max_length=128, description="Secure password")
    turnstile_token: Optional[str] = Field(None, description="Cloudflare Turnstile challenge token")


class UserLoginRequest(BaseModel):
    """Request payload to authenticate with email or username and password."""
    model_config = ConfigDict(extra="ignore")

    email: str = Field(..., min_length=2, max_length=255, description="Valid email address or username")
    password: str = Field(..., min_length=1, max_length=128, description="Master password")
    turnstile_token: Optional[str] = Field(None, description="Cloudflare Turnstile challenge token")


class GoogleAuthRequest(BaseModel):
    """Request payload to authenticate via Google GIS ID token."""
    model_config = ConfigDict(extra="ignore")

    id_token: str = Field(..., min_length=10, description="Google OAuth2 ID token / credential")
    turnstile_token: Optional[str] = Field(None, description="Cloudflare Turnstile challenge token")


class ForgotPasswordRequest(BaseModel):
    """Request payload for forgotten password dispatch."""
    model_config = ConfigDict(extra="ignore")

    email: str = Field(..., min_length=2, max_length=255, description="Valid email address or username")
    turnstile_token: Optional[str] = Field(None, description="Cloudflare Turnstile challenge token")


class ResetPasswordRequest(BaseModel):
    """Request payload to finalize password reset using signed token."""
    model_config = ConfigDict(extra="ignore")

    token: str = Field(..., min_length=10, description="Cryptographic password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New secure password")
    turnstile_token: Optional[str] = Field(None, description="Cloudflare Turnstile challenge token")


class PasswordResetResponse(BaseModel):
    """Status response for password reset operations."""
    status: str
    message: str
    reset_token: Optional[str] = None


class AuthResponse(BaseModel):
    """JWT authorization response returned upon successful authentication (5-min access + 7-day refresh)."""
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Request payload to exchange a refresh token for a fresh access token (optional if provided via cookie)."""
    model_config = ConfigDict(extra="ignore")

    refresh_token: Optional[str] = Field(None, description="Cryptographic refresh token (optional if sent via HttpOnly cookie)")


class RefreshTokenRecord(BaseModel):
    """Schema representing stored refresh token metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    jti: str
    expires_at: datetime
    is_revoked: bool
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime


class LogoutRequest(BaseModel):
    """Request payload to revoke tokens on logout."""
    model_config = ConfigDict(extra="ignore")

    refresh_token: Optional[str] = Field(None, description="Optional refresh token to explicitly revoke")


class UserSessionResponse(BaseModel):
    """Active device/session information for account security settings."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_name: str
    device_type: str = "desktop"  # desktop, mobile, tablet
    ip_address: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    is_current: bool = False


class RevokeSessionsRequest(BaseModel):
    """Request payload to terminate sessions."""
    model_config = ConfigDict(extra="ignore")

    keep_current: bool = Field(False, description="Whether to keep the current device session active")
