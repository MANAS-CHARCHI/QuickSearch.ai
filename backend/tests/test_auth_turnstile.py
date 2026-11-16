import pytest
from datetime import timedelta
import time
from fastapi import HTTPException
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.core.limiter import SlidingWindowRateLimiter
from app.core.turnstile import verify_turnstile_token


def test_password_hashing():
    pw = "SuperSecurePassword123!"
    hashed = get_password_hash(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_creation_and_decoding():
    data = {"sub": "12345-uuid", "email": "test@vaultcity.ai", "role": "user"}
    token = create_access_token(data=data, expires_delta=timedelta(minutes=5))
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    decoded = decode_access_token(token)
    assert decoded["sub"] == "12345-uuid"
    assert decoded["email"] == "test@vaultcity.ai"
    assert decoded["role"] == "user"


def test_jwt_token_expiration():
    data = {"sub": "expired-user"}
    # Token that expired 5 seconds ago
    token = create_access_token(data=data, expires_delta=timedelta(seconds=-5))
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter(cleanup_interval_seconds=60)
    
    # Mock dummy request and response
    class DummyRequest:
        headers = {"x-forwarded-for": "203.0.113.195"}
        client = None

    class DummyResponse:
        headers = {}

    req = DummyRequest()
    res = DummyResponse()

    # Allowed 3 requests in 10-second window
    await limiter.check(req, res, max_requests=3, window_seconds=10, key_prefix="test")
    assert res.headers["X-RateLimit-Limit"] == "3"
    assert res.headers["X-RateLimit-Remaining"] == "2"

    await limiter.check(req, res, max_requests=3, window_seconds=10, key_prefix="test")
    assert res.headers["X-RateLimit-Remaining"] == "1"

    await limiter.check(req, res, max_requests=3, window_seconds=10, key_prefix="test")
    assert res.headers["X-RateLimit-Remaining"] == "0"

    # 4th request must raise 429
    with pytest.raises(HTTPException) as exc_info:
        await limiter.check(req, res, max_requests=3, window_seconds=10, key_prefix="test")
    assert exc_info.value.status_code == 429
    assert "Retry-After" in res.headers


@pytest.mark.asyncio
async def test_turnstile_token_validation_guards():
    # Empty token raises 400
    with pytest.raises(HTTPException) as exc_info:
        await verify_turnstile_token(token="")
    assert exc_info.value.status_code == 400

    # Overly long token raises 400
    with pytest.raises(HTTPException) as exc_info:
        await verify_turnstile_token(token="A" * 3000)
    assert exc_info.value.status_code == 400


def test_google_auth_request_schema():
    from app.schemas.auth import GoogleAuthRequest
    from pydantic import ValidationError

    # Valid schema
    req = GoogleAuthRequest(id_token="valid_sample_google_jwt_token_12345", turnstile_token="turnstile_sample")
    assert req.id_token == "valid_sample_google_jwt_token_12345"
    assert req.turnstile_token == "turnstile_sample"

    # Too short id_token raises ValidationError
    with pytest.raises(ValidationError):
        GoogleAuthRequest(id_token="short")


def test_password_reset_token_lifecycle():
    from app.core.security import create_password_reset_token, verify_password_reset_token, create_access_token
    from app.schemas.auth import ResetPasswordRequest

    email = "user@vaultcity.ai"
    user_id = "550e8400-e29b-41d4-a716-446655440000"

    # Create reset token
    reset_token = create_password_reset_token(email=email, user_id=user_id)
    assert isinstance(reset_token, str)

    # Verify reset token
    payload = verify_password_reset_token(reset_token)
    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload["type"] == "pwd_reset"

    # Regular access token must fail when used as password reset token
    access_token = create_access_token(data={"sub": user_id, "email": email, "type": "access"})
    with pytest.raises(HTTPException) as exc_info:
        verify_password_reset_token(access_token)
    assert exc_info.value.status_code == 400
    assert "Invalid token purpose" in exc_info.value.detail

    # Test ResetPasswordRequest schema validation
    reset_req = ResetPasswordRequest(
        token=reset_token,
        new_password="BrandNewSecurePassword456!",
        turnstile_token="sample_cf_token",
    )
    assert reset_req.token == reset_token
    assert reset_req.new_password == "BrandNewSecurePassword456!"


def test_username_schemas_and_defaults():
    from app.schemas.user import UpdateProfileRequest, UserResponse
    from app.schemas.auth import UserRegisterRequest
    from datetime import datetime

    # UserRegisterRequest with custom username
    reg_with_username = UserRegisterRequest(
        email="alex@vaultcity.ai",
        username="alex_custom",
        password="ValidPassword123!",
    )
    assert reg_with_username.username == "alex_custom"

    # UserRegisterRequest with default (None)
    reg_without_username = UserRegisterRequest(
        email="bob@vaultcity.ai",
        password="ValidPassword123!",
    )
    assert reg_without_username.username is None

    # UpdateProfileRequest validation
    update_req = UpdateProfileRequest(username="alex_updated")
    assert update_req.username == "alex_updated"

    # UserResponse includes username
    user_resp = UserResponse(
        id="test-uuid",
        email="alex@vaultcity.ai",
        username="alex_updated",
        role="user",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    assert user_resp.username == "alex_updated"


def test_make_user_response_social_and_password_flags():
    from app.schemas.user import make_user_response
    from app.models.user import User
    from datetime import datetime
    import uuid

    # User created via Google OAuth only
    google_user = User(
        id=uuid.uuid4(),
        email="googleuser@vaultcity.ai",
        username="Google User",
        hashed_password=None,
        google_id="google-sub-12345",
        role="user",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    resp = make_user_response(google_user)
    assert resp.has_google is True
    assert resp.has_password is False

    # User created via email/password only
    password_user = User(
        id=uuid.uuid4(),
        email="passuser@vaultcity.ai",
        username="Password User",
        hashed_password="bcrypt$hashed$password",
        google_id=None,
        role="user",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    resp = make_user_response(password_user)
    assert resp.has_google is False
    assert resp.has_password is True

    # User linked with both
    linked_user = User(
        id=uuid.uuid4(),
        email="linked@vaultcity.ai",
        username="Linked User",
        hashed_password="bcrypt$hashed$password",
        google_id="google-sub-67890",
        role="user",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    resp = make_user_response(linked_user)
    assert resp.has_google is True
    assert resp.has_password is True


def test_change_password_request_schema():
    from app.schemas.user import ChangePasswordRequest

    req = ChangePasswordRequest(
        current_password="OldPassword123!",
        new_password="NewSecurePassword456!",
    )
    assert req.current_password == "OldPassword123!"
    assert req.new_password == "NewSecurePassword456!"

    # Allowed without current_password for Google OAuth users configuring first password
    req_no_curr = ChangePasswordRequest(new_password="BrandNewPassword123!")
    assert req_no_curr.current_password is None
    assert req_no_curr.new_password == "BrandNewPassword123!"


def test_all_schemas_importable_from_package():
    import app.schemas as schemas

    assert hasattr(schemas, "TurnstileVerifyRequest")
    assert hasattr(schemas, "TurnstileVerifyResponse")
    assert hasattr(schemas, "UserBase")
    assert hasattr(schemas, "UserResponse")
    assert hasattr(schemas, "UpdateProfileRequest")
    assert hasattr(schemas, "ChangePasswordRequest")
    assert hasattr(schemas, "make_user_response")
    assert hasattr(schemas, "UserRegisterRequest")
    assert hasattr(schemas, "UserLoginRequest")
    assert hasattr(schemas, "GoogleAuthRequest")
    assert hasattr(schemas, "ForgotPasswordRequest")
    assert hasattr(schemas, "ResetPasswordRequest")
    assert hasattr(schemas, "AuthResponse")
    assert hasattr(schemas, "FileDocumentCreate")
    assert hasattr(schemas, "FileDocumentResponse")
    assert hasattr(schemas, "ChatMessageCreate")
    assert hasattr(schemas, "ConversationResponse")
    assert hasattr(schemas, "AuditLogCreate")
    assert hasattr(schemas, "AuditLogResponse")
