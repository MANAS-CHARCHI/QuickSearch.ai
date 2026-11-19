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
    import uuid

    limiter = SlidingWindowRateLimiter(cleanup_interval_seconds=60)
    unique_prefix = f"test_{uuid.uuid4().hex[:8]}"

    # Mock dummy request and response
    class DummyRequest:
        headers = {"x-forwarded-for": "203.0.113.195"}
        client = None

    class DummyResponse:
        def __init__(self):
            self.headers = {}

    req = DummyRequest()
    res = DummyResponse()

    # Allowed 3 requests in 10-second window
    await limiter.check(req, res, max_requests=3, window_seconds=10, key_prefix=unique_prefix)
    assert res.headers["X-RateLimit-Limit"] == "3"
    assert res.headers["X-RateLimit-Remaining"] == "2"

    await limiter.check(req, res, max_requests=3, window_seconds=10, key_prefix=unique_prefix)
    assert res.headers["X-RateLimit-Remaining"] == "1"

    await limiter.check(req, res, max_requests=3, window_seconds=10, key_prefix=unique_prefix)
    assert res.headers["X-RateLimit-Remaining"] == "0"

    # 4th request must raise 429
    with pytest.raises(HTTPException) as exc_info:
        await limiter.check(req, res, max_requests=3, window_seconds=10, key_prefix=unique_prefix)
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

    # Test reset token with username saved
    username = "alex_vault"
    reset_token_with_user = create_password_reset_token(email=email, user_id=user_id, username=username)
    payload_user = verify_password_reset_token(reset_token_with_user)
    assert payload_user["username"] == username
    assert payload_user["sub"] == user_id
    assert payload_user["email"] == email

    # Verify access token generated with username saved
    from app.core.security import decode_access_token
    access_token_with_username = create_access_token(
        data={"sub": user_id, "email": email, "username": username, "role": "user"}
    )
    access_payload = decode_access_token(access_token_with_username)
    assert access_payload["username"] == username
    assert access_payload["sub"] == user_id
    assert access_payload["type"] == "access"

    # Verify ForgotPasswordRequest and UserLoginRequest allow username as identifier
    from app.schemas.auth import ForgotPasswordRequest, UserLoginRequest
    forgot_req = ForgotPasswordRequest(email="alex_vault")
    assert forgot_req.email == "alex_vault"
    login_req = UserLoginRequest(email="alex_vault", password="MySecurePassword123!")
    assert login_req.email == "alex_vault"


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
    assert hasattr(schemas, "RefreshTokenRequest")
    assert hasattr(schemas, "LogoutRequest")
    assert hasattr(schemas, "FileDocumentCreate")
    assert hasattr(schemas, "FileDocumentResponse")
    assert hasattr(schemas, "ChatMessageCreate")
    assert hasattr(schemas, "ConversationResponse")
    assert hasattr(schemas, "AuditLogCreate")
    assert hasattr(schemas, "AuditLogResponse")


def test_access_and_refresh_token_durations():
    from app.core.security import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token

    user_data = {"sub": "user-uuid-1234", "email": "test@vault.city", "role": "user"}

    # 1. 5-Minute Access Token Verification
    access_token = create_access_token(data=user_data, expires_delta=timedelta(minutes=5))
    access_payload = decode_access_token(access_token)
    assert access_payload["sub"] == "user-uuid-1234"
    assert access_payload["type"] == "access"
    assert "jti" in access_payload
    # Expiration is within 5 minutes (300 seconds +/- 10s)
    exp_diff = access_payload["exp"] - access_payload["iat"]
    assert 290 <= exp_diff <= 310

    # 2. 7-Day Refresh Token Verification
    refresh_token = create_refresh_token(data=user_data)
    refresh_payload = decode_refresh_token(refresh_token)
    assert refresh_payload["sub"] == "user-uuid-1234"
    assert refresh_payload["type"] == "refresh"
    assert "jti" in refresh_payload
    # Expiration is within 7 days (604,800 seconds +/- 60s)
    refresh_diff = refresh_payload["exp"] - refresh_payload["iat"]
    assert 604700 <= refresh_diff <= 604900

    # 3. Type Isolation Guard: decode_refresh_token must reject access token
    with pytest.raises(HTTPException) as exc_info:
        decode_refresh_token(access_token)
    assert exc_info.value.status_code == 401
    assert "Invalid token type" in exc_info.value.detail


@pytest.mark.asyncio
async def test_redis_token_hash_map_lifecycle():
    from app.core.redis import (
        store_refresh_token,
        check_refresh_token_in_redis,
        revoke_refresh_token,
        revoke_all_user_refresh_tokens,
        get_refresh_token_metadata,
    )
    import uuid
    import time

    jti_refresh = uuid.uuid4().hex
    user_id = str(uuid.uuid4())
    now = int(time.time())

    # Store 7-day refresh token in Redis map with TTL
    await store_refresh_token(
        jti=jti_refresh,
        user_id=user_id,
        exp_timestamp=now + 604800,
    )
    assert await check_refresh_token_in_redis(jti_refresh, user_id=user_id) is True

    meta = await get_refresh_token_metadata(jti_refresh)
    assert meta is not None
    assert meta["jti"] == jti_refresh
    assert meta["sub"] == user_id

    # Revoke single refresh token
    await revoke_refresh_token(jti_refresh, user_id=user_id)
    assert await check_refresh_token_in_redis(jti_refresh, user_id=user_id) is False

    # Second token for user
    jti_refresh_2 = uuid.uuid4().hex
    await store_refresh_token(
        jti=jti_refresh_2,
        user_id=user_id,
        exp_timestamp=now + 604800,
    )
    assert await check_refresh_token_in_redis(jti_refresh_2, user_id=user_id) is True

    # Revoke all user tokens
    await revoke_all_user_refresh_tokens(user_id)
    assert await check_refresh_token_in_redis(jti_refresh_2, user_id=user_id) is False


def test_auth_response_dual_token_schema():
    from app.schemas.auth import AuthResponse, RefreshTokenRequest, LogoutRequest
    from app.schemas.user import UserResponse
    from datetime import datetime

    user_resp = UserResponse(
        id="usr-123",
        email="test@vault.city",
        role="user",
        is_active=True,
        created_at=datetime.utcnow(),
    )

    auth_resp = AuthResponse(
        access_token="sample_access_jwt",
        refresh_token="sample_refresh_jwt",
        token_type="bearer",
        user=user_resp,
    )
    assert auth_resp.access_token == "sample_access_jwt"
    assert auth_resp.refresh_token == "sample_refresh_jwt"
    assert auth_resp.token_type == "bearer"

    refresh_req = RefreshTokenRequest(refresh_token="sample_refresh_jwt_123456")
    assert refresh_req.refresh_token == "sample_refresh_jwt_123456"

    logout_req = LogoutRequest(refresh_token="sample_refresh_jwt_123456")
    assert logout_req.refresh_token == "sample_refresh_jwt_123456"


@pytest.mark.asyncio
async def test_redis_distributed_rate_limiter_multi_instance():
    """
    Simulate two independent backend instances powered by pylimitx sharing a single Redis backend.
    Both instances must enforce one unified distributed sliding-window rate limit.
    """
    class FakeSharedRedis:
        def __init__(self):
            self.zsets = {}
            self.ttls = {}

        async def eval(self, script, numkeys, key, limit, window_sec, now_ms, request_id):
            limit = int(limit)
            window_ms = int(window_sec) * 1000
            now_ms = int(now_ms)
            cutoff = now_ms - window_ms

            entries = self.zsets.get(key, {})
            entries = {m: score for m, score in entries.items() if score > cutoff}
            self.zsets[key] = entries

            count = len(entries)
            if count >= limit:
                return [0, 0, self.ttls.get(key, window_ms)]

            entries[request_id] = now_ms
            self.ttls[key] = window_ms
            return [1, limit - count - 1, -1]

    shared_redis = FakeSharedRedis()
    # Two separate backend instance limiters pointing to the same Redis
    instance_a = SlidingWindowRateLimiter(redis_client=shared_redis)
    instance_b = SlidingWindowRateLimiter(redis_client=shared_redis)

    class DummyRequest:
        def __init__(self, ip: str):
            self.headers = {"x-forwarded-for": ip}
            self.client = None

    class DummyResponse:
        def __init__(self):
            self.headers = {}

    req_client_1 = DummyRequest("198.51.100.10")
    res = DummyResponse()

    # Request 1 hits Instance A
    await instance_a.check(req_client_1, res, max_requests=3, window_seconds=30, key_prefix="auth_login")
    assert res.headers["X-RateLimit-Limit"] == "3"
    assert res.headers["X-RateLimit-Remaining"] == "2"

    # Request 2 hits Instance B (shared Redis sees count=1 -> becomes 2)
    await instance_b.check(req_client_1, res, max_requests=3, window_seconds=30, key_prefix="auth_login")
    assert res.headers["X-RateLimit-Remaining"] == "1"

    # Request 3 hits Instance A (shared Redis sees count=2 -> becomes 3)
    await instance_a.check(req_client_1, res, max_requests=3, window_seconds=30, key_prefix="auth_login")
    assert res.headers["X-RateLimit-Remaining"] == "0"

    # Request 4 hits Instance B -> must be blocked globally with 429!
    with pytest.raises(HTTPException) as exc_info:
        await instance_b.check(req_client_1, res, max_requests=3, window_seconds=30, key_prefix="auth_login")
    assert exc_info.value.status_code == 429
    assert "Retry-After" in res.headers
    assert shared_redis.ttls["pylimitx:auth_login:198.51.100.10"] == 30000

    # A different client IP must still be allowed on Instance B
    req_client_2 = DummyRequest("198.51.100.20")
    res2 = DummyResponse()
    await instance_b.check(req_client_2, res2, max_requests=3, window_seconds=30, key_prefix="auth_login")
    assert res2.headers["X-RateLimit-Remaining"] == "2"


@pytest.mark.asyncio
async def test_redis_rate_limiter_circuit_breaker_fail_open():
    """If Redis raises errors, pylimitx CircuitBreaker trips OPEN and fails open gracefully."""
    class BrokenRedis:
        def __init__(self):
            self.calls = 0

        async def eval(self, *args, **kwargs):
            self.calls += 1
            raise ConnectionError("Redis connection refused")

    broken_redis = BrokenRedis()
    limiter = SlidingWindowRateLimiter(
        redis_client=broken_redis,
        fail_open=True,
        failure_threshold=2,
        recovery_timeout=30,
    )

    class DummyRequest:
        headers = {"x-forwarded-for": "198.51.100.99"}
        client = None

    class DummyResponse:
        def __init__(self):
            self.headers = {}

    req = DummyRequest()
    res = DummyResponse()

    # First 2 calls hit Redis and fail -> CircuitBreaker trips to OPEN
    await limiter.check(req, res, max_requests=2, window_seconds=10, key_prefix="cb_test")
    await limiter.check(req, res, max_requests=2, window_seconds=10, key_prefix="cb_test")
    assert limiter._get_engine().circuit_breaker.is_open is True
    assert broken_redis.calls == 2

    # 3rd call short-circuits in OPEN state without even calling Redis
    await limiter.check(req, res, max_requests=2, window_seconds=10, key_prefix="cb_test")
    assert broken_redis.calls == 2


@pytest.mark.asyncio
async def test_email_otp_generation_and_verification_lifecycle():
    """Verify 6-digit OTP generation, hashed storage, single-use verification, attempt limits, and cooldown."""
    import uuid
    from app.core.redis import (
        generate_numeric_otp,
        store_email_otp,
        verify_email_otp,
        get_email_otp_resend_cooldown,
    )

    email = f"otp_test_{uuid.uuid4().hex[:8]}@vault.city"
    otp = generate_numeric_otp(6)
    assert len(otp) == 6
    assert otp.isdigit()

    await store_email_otp(email, otp, ttl_seconds=300)

    # Cooldown must be active right after storing
    cooldown = await get_email_otp_resend_cooldown(email, cooldown_seconds=60)
    assert 50 <= cooldown <= 60

    # Wrong OTP fails with "invalid"
    wrong_otp = "000000" if otp != "000000" else "999999"
    ok, reason = await verify_email_otp(email, wrong_otp, max_attempts=3)
    assert ok is False
    assert reason == "invalid"

    # Correct OTP succeeds and is immediately consumed (single-use)
    ok, reason = await verify_email_otp(email, otp, max_attempts=3)
    assert ok is True
    assert reason == "verified"

    # Replaying the same OTP fails with "expired"
    ok, reason = await verify_email_otp(email, otp, max_attempts=3)
    assert ok is False
    assert reason == "expired"

    # Exceeding max attempts invalidates the OTP
    otp2 = generate_numeric_otp(6)
    await store_email_otp(email, otp2, ttl_seconds=300)
    wrong2 = "111111" if otp2 != "111111" else "222222"
    assert (await verify_email_otp(email, wrong2, max_attempts=2)) == (False, "invalid")
    assert (await verify_email_otp(email, wrong2, max_attempts=2)) == (False, "max_attempts")
    assert (await verify_email_otp(email, otp2, max_attempts=2)) == (False, "expired")


@pytest.mark.asyncio
async def test_email_otp_schemas_and_smtp_fallback(monkeypatch):
    """Validate OTP request schemas and SMTP email dispatch fallback when credentials are unset."""
    from pydantic import ValidationError
    from app.schemas.auth import VerifyEmailOTPRequest, ResendOTPRequest, RegisterResponse
    from app.services import email_service
    from app.core.config import settings

    # Valid 6-digit OTP
    req = VerifyEmailOTPRequest(email="alice@vault.city", otp="042819")
    assert req.otp == "042819"

    # Non-6-digit or non-numeric OTP raises ValidationError
    with pytest.raises(ValidationError):
        VerifyEmailOTPRequest(email="alice@vault.city", otp="12345")
    with pytest.raises(ValidationError):
        VerifyEmailOTPRequest(email="alice@vault.city", otp="abcdef")

    resend = ResendOTPRequest(email="alice@vault.city")
    assert resend.email == "alice@vault.city"

    reg_resp = RegisterResponse(
        email="alice@vault.city",
        message="OTP sent",
        expires_in_seconds=600,
    )
    assert reg_resp.verification_required is True

    # Test console fallback when SMTP credentials are not configured
    monkeypatch.setattr(settings, "SMTP_USERNAME", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)
    assert email_service.is_smtp_configured() is False

    otp_delivery = await email_service.send_verification_otp_email(
        to_email="alice@vault.city",
        username="alice",
        otp_code="042819",
    )
    assert otp_delivery["mode"] == "console_fallback"

    reset_delivery = await email_service.send_password_reset_email(
        to_email="alice@vault.city",
        username="alice",
        reset_token="sample-reset-token-12345",
    )
    assert reset_delivery["mode"] == "console_fallback"


@pytest.mark.asyncio
async def test_email_otp_resend_quota_counter():
    """Verify per-email OTP resend counter increments up to cap and clears on verification."""
    import uuid
    from app.core.redis import (
        get_email_otp_resend_count,
        increment_email_otp_resend_count,
        clear_email_otp_resend_count,
    )

    email = f"resend_quota_{uuid.uuid4().hex[:8]}@vault.city"
    assert await get_email_otp_resend_count(email) == 0

    for expected in range(1, 6):
        used = await increment_email_otp_resend_count(email, window_seconds=3600)
        assert used == expected
    assert await get_email_otp_resend_count(email) == 5

    await clear_email_otp_resend_count(email)
    assert await get_email_otp_resend_count(email) == 0




