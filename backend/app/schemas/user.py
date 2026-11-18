"""
Pydantic schemas for User profiles, password management, and account settings.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    """Shared user properties."""
    email: str = Field(..., min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="Valid user email address")
    username: Optional[str] = Field(None, min_length=2, max_length=100, description="Display username")
    role: str = Field("user", max_length=50, description="Account role")
    is_active: bool = Field(True, description="Account active status")


class UserResponse(BaseModel):
    """User profile response including social auth, email verification, and master password status."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: Optional[str] = None
    role: str
    is_active: bool
    is_email_verified: bool = True
    has_google: bool = False
    has_password: bool = False
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    """Request to update display username."""
    model_config = ConfigDict(extra="ignore")

    username: str = Field(..., min_length=2, max_length=100, description="New display username")


class ChangePasswordRequest(BaseModel):
    """Request to configure or change master password."""
    model_config = ConfigDict(extra="ignore")

    current_password: Optional[str] = Field(None, min_length=1, max_length=128, description="Current master password (optional if setting password for first time)")
    new_password: str = Field(..., min_length=8, max_length=128, description="New secure password")


def make_user_response(user) -> UserResponse:
    """
    Canonical serializer converting SQLAlchemy User model to UserResponse,
    accurately computing has_google and has_password boolean flags.
    """
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username or user.email.split("@")[0],
        role=user.role,
        is_active=user.is_active,
        is_email_verified=bool(getattr(user, "is_email_verified", True)),
        has_google=bool(getattr(user, "google_id", None)),
        has_password=bool(getattr(user, "hashed_password", None)),
        created_at=user.created_at,
    )
