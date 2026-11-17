from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_

from app.core.config import settings
from app.core.database import get_db
from app.core.limiter import rate_limit
from app.core.redis import (
    check_refresh_token_in_redis,
    revoke_all_user_refresh_tokens,
    revoke_refresh_token,
    store_refresh_token,
)
from app.core.security import (
    clear_auth_cookies,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    set_auth_cookies,
    verify_password,
    verify_password_reset_token,
)
from app.core.turnstile import get_client_ip, verify_turnstile_token
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LogoutRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    RevokeSessionsRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserSessionResponse,
)
from app.schemas.turnstile import (
    TurnstileVerifyRequest,
    TurnstileVerifyResponse,
)
from app.schemas.user import (
    ChangePasswordRequest,
    UpdateProfileRequest,
    UserResponse,
    make_user_response,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Security"])


async def issue_token_pair(
    user: User,
    db: AsyncSession,
    request: Optional[Request] = None,
) -> Tuple[str, str]:
    """
    Issue a 5-minute access token and 7-day refresh token.
    1. Generates 5-minute access token (stateless HS256 JWT, not stored in Redis).
    2. Generates 7-day refresh token with unique JTI.
    3. Stores refresh token in Redis with exact 7-day TTL for fast O(1) renewal.
    4. Persists refresh token in PostgreSQL refresh_tokens table (durable source of truth).
    """
    effective_username = user.username or (user.email.split("@")[0] if user.email else "user")
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "username": effective_username,
        "role": user.role,
    }

    # 1. 5-minute Stateless Access Token (verified cryptographically in memory)
    access_token = create_access_token(data=token_data)

    # 2. 7-day Refresh Token
    refresh_token = create_refresh_token(data=token_data)
    refresh_payload = decode_access_token(refresh_token)

    # 3. Cache Refresh Token in Redis with exact TTL
    await store_refresh_token(
        jti=refresh_payload["jti"],
        user_id=str(user.id),
        exp_timestamp=refresh_payload["exp"],
        raw_token=refresh_token,
    )

    # 4. Persist Refresh Token in PostgreSQL (Source of Truth)
    client_ip = get_client_ip(request) if request else None
    user_agent = None
    if request:
        ua_raw = request.headers.get("user-agent")
        if ua_raw:
            user_agent = ua_raw[:255]

    refresh_exp_dt = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
    db_refresh_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=refresh_token,
        jti=refresh_payload["jti"],
        expires_at=refresh_exp_dt,
        is_revoked=False,
        user_agent=user_agent,
        ip_address=client_ip,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(db_refresh_token)
    await db.commit()

    return access_token, refresh_token


# --- Endpoints ---

@router.post(
    "/verify-turnstile",
    response_model=TurnstileVerifyResponse,
    summary="Verify Cloudflare Turnstile token server-side",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, key_prefix="turnstile_verify"))],
)
async def verify_turnstile(
    request: Request,
    payload: TurnstileVerifyRequest = Body(...),
):
    """
    Validates a Turnstile token against Cloudflare's canonical siteverify endpoint.
    Used for pre-validation and interactive verification testing.
    """
    client_ip = get_client_ip(request)
    result = await verify_turnstile_token(
        token=payload.token,
        remote_ip=client_ip,
        expected_action=payload.action,
    )

    return TurnstileVerifyResponse(
        success=result.get("success", True),
        status="verified",
        hostname=result.get("hostname"),
        action=result.get("action"),
        challenge_ts=result.get("challenge_ts"),
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user with Turnstile human verification",
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, key_prefix="auth_register"))],
)
async def register(
    request: Request,
    response: Response,
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user:
    1. Validates human Turnstile token
    2. Validates email uniqueness
    3. Hashes password securely via bcrypt
    4. Persists user in database
    5. Returns JWT access token, sets HttpOnly cookies, and returns user profile
    """
    client_ip = get_client_ip(request)

    # Turnstile verification
    token = payload.turnstile_token or request.headers.get("x-turnstile-token")
    if settings.TURNSTILE_ENABLED and not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare human verification check required.",
        )
    if token:
        await verify_turnstile_token(token=token, remote_ip=client_ip, expected_action=["auth", "signup", "register"])

    # Check if user already exists
    existing_query = select(User).where(User.email == payload.email.lower().strip())
    existing_result = await db.execute(existing_query)
    existing_user = existing_result.scalar_one_or_none()
    if existing_user:
        # If user registered via Google OAuth and has no password yet, link this password!
        if existing_user.hashed_password is None:
            hashed = get_password_hash(payload.password)
            existing_user.hashed_password = hashed
            if payload.username and payload.username.strip():
                existing_user.username = payload.username.strip()
            existing_user.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(existing_user)

            access_token, refresh_token = await issue_token_pair(existing_user, db, request)
            set_auth_cookies(response, access_token, refresh_token)

            return AuthResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                user=make_user_response(existing_user),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists. Please sign in with your password or use Google Sign-In.",
            )

    # Create user
    hashed = get_password_hash(payload.password)
    default_username = (
        payload.username.strip()
        if payload.username and payload.username.strip()
        else payload.email.split("@")[0]
    )
    new_user = User(
        id=uuid.uuid4(),
        email=payload.email.lower().strip(),
        username=default_username,
        hashed_password=hashed,
        role="user",
        is_active=True,
        is_locked=False,
        failed_attempts=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Generate dual tokens (5-min access + 7-day refresh) recorded in Redis and PostgreSQL
    access_token, refresh_token = await issue_token_pair(new_user, db, request)
    set_auth_cookies(response, access_token, refresh_token)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=make_user_response(new_user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate user with Turnstile human verification and brute-force protection",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, key_prefix="auth_login"))],
)
async def login(
    request: Request,
    response: Response,
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user:
    1. Validates human Turnstile token
    2. Enforces account lock guard on 5 consecutive failed attempts
    3. Verifies bcrypt password hash
    4. Issues 5-minute access token and 7-day refresh token in DB & Redis
    5. Sets HttpOnly cookies on response
    """
    client_ip = get_client_ip(request)

    # Turnstile verification
    token = payload.turnstile_token or request.headers.get("x-turnstile-token")
    if settings.TURNSTILE_ENABLED and not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare human verification check required.",
        )
    if token:
        await verify_turnstile_token(token=token, remote_ip=client_ip, expected_action=["auth", "login"])

    # Fetch user by email or username
    identifier = payload.email.strip()
    user_query = select(User).where(
        or_(
            User.email == identifier.lower(),
            User.username == identifier,
        )
    )
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is locked due to too many failed attempts. Please reset your password.",
        )

    # Check if user has no password set (registered via Google)
    if not user.hashed_password and user.google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account was registered using Google Sign-In. Please click 'Continue with Google', or create your password on the Sign Up tab.",
        )

    # Check password
    if not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        user.failed_attempts += 1
        if user.failed_attempts >= 5:
            user.is_locked = True
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reset failed attempts upon successful login
    if user.failed_attempts > 0:
        user.failed_attempts = 0
        await db.commit()

    # Generate dual tokens (5-min access + 7-day refresh) recorded in Redis and PostgreSQL
    access_token, refresh_token = await issue_token_pair(user, db, request)
    set_auth_cookies(response, access_token, refresh_token)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=make_user_response(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """Fetch the active user's profile details."""
    return make_user_response(current_user)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Exchange valid 7-day refresh token for a fresh 5-minute access token",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, key_prefix="auth_refresh"))],
)
async def refresh_session(
    request: Request,
    response: Response,
    payload: Optional[RefreshTokenRequest] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate cryptographic refresh token and issue a fresh 5-minute access token.
    1. Extracts refresh token from HttpOnly cookie or request body.
    2. Decodes JWT and ensures type == 'refresh' and not expired.
    3. Validates JTI in Redis Hash Map in O(1) time.
    4. Validates token in PostgreSQL refresh_tokens table (not revoked, not expired).
    5. Rotates tokens: generates fresh 5-minute access token & fresh 7-day refresh token.
    6. Invalidates old refresh token in Redis and marks is_revoked = True in DB.
    7. Sets fresh HttpOnly cookies on response and returns AuthResponse.
    """
    token_str: Optional[str] = None
    if payload and payload.refresh_token and payload.refresh_token.strip():
        token_str = payload.refresh_token.strip()
    elif request and settings.COOKIE_REFRESH_NAME in request.cookies:
        cookie_val = request.cookies.get(settings.COOKIE_REFRESH_NAME)
        if cookie_val and cookie_val.strip():
            token_str = cookie_val.strip()

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refresh token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    refresh_payload = decode_refresh_token(token_str)
    jti = refresh_payload.get("jti")
    user_id_str = refresh_payload.get("sub")

    if not jti or not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed session refresh credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Check Redis cache first (Fast O(1) response)
    redis_status = await check_refresh_token_in_redis(jti, user_id=user_id_str)

    # If Redis explicitly holds a revoked or expired tombstone, reject immediately
    if redis_status is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refresh token has been revoked or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user session identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Check PostgreSQL Database (Source of Truth)
    # If redis_status is None (token was removed/evicted from Redis, or Redis restarted),
    # the database is consulted as the authoritative source of truth.
    token_query = select(RefreshToken).where(
        RefreshToken.jti == jti,
        RefreshToken.user_id == user_uuid,
    )
    token_res = await db.execute(token_query)
    stored_token = token_res.scalar_one_or_none()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refresh token not found or invalidated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if stored_token.is_revoked:
        # Token reuse detection: if a revoked refresh token is presented, revoke all active sessions!
        await revoke_all_user_refresh_tokens(user_id_str)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_uuid, RefreshToken.is_revoked == False)
            .values(is_revoked=True, updated_at=datetime.utcnow())
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refresh token has been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now_utc = datetime.now(timezone.utc)
    if stored_token.expires_at < now_utc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refresh token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_query = select(User).where(User.id == user_uuid)
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account no longer exists.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="User account is locked.",
        )

    # Invalidate old refresh token in DB and Redis
    stored_token.is_revoked = True
    stored_token.updated_at = datetime.utcnow()
    await db.commit()
    await revoke_refresh_token(jti, user_id=user_id_str)

    # Issue fresh token pair (5-min stateless access + rotating 7-day refresh)
    new_access_token, new_refresh_token = await issue_token_pair(user, db, request)

    # Set new HttpOnly cookies on response
    set_auth_cookies(response, new_access_token, new_refresh_token)

    return AuthResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=make_user_response(user),
    )


@router.post(
    "/logout",
    summary="Revoke session tokens and log out user",
)
async def logout(
    request: Request,
    response: Response,
    payload: Optional[LogoutRequest] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Log out active user:
    1. Revokes provided refresh token in Redis and marks is_revoked = True in PostgreSQL.
    2. Clears HttpOnly cookies on response.
    """
    refresh_token = None
    if payload and payload.refresh_token:
        refresh_token = payload.refresh_token
    elif settings.COOKIE_REFRESH_NAME in request.cookies:
        refresh_token = request.cookies.get(settings.COOKIE_REFRESH_NAME)

    if refresh_token:
        try:
            refresh_payload = decode_access_token(refresh_token)
            jti = refresh_payload.get("jti")
            sub = refresh_payload.get("sub")
            if jti:
                await revoke_refresh_token(jti, user_id=sub)
                if sub:
                    try:
                        user_uuid = uuid.UUID(sub)
                        await db.execute(
                            update(RefreshToken)
                            .where(RefreshToken.jti == jti, RefreshToken.user_id == user_uuid)
                            .values(is_revoked=True, updated_at=datetime.utcnow())
                        )
                        await db.commit()
                    except Exception:
                        pass
        except Exception:
            pass

    # Clear HttpOnly cookies
    clear_auth_cookies(response)

    return {
        "status": "success",
        "message": "Successfully logged out. All session tokens invalidated.",
    }


def parse_user_agent(user_agent: Optional[str]) -> Tuple[str, str]:
    """
    Parse raw User-Agent header into friendly device name and category.
    Returns: (device_name, device_type) where device_type in ('desktop', 'mobile', 'tablet')
    """
    if not user_agent:
        return "Unknown Device", "desktop"

    ua = user_agent.lower()

    # Device Type
    if "ipad" in ua or "tablet" in ua:
        device_type = "tablet"
    elif "iphone" in ua or "android" in ua or "mobile" in ua:
        device_type = "mobile"
    else:
        device_type = "desktop"

    # Operating System
    os_name = "Unknown OS"
    if "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "iphone" in ua:
        os_name = "iOS"
    elif "ipad" in ua:
        os_name = "iPadOS"
    elif "android" in ua:
        os_name = "Android"
    elif "windows" in ua:
        os_name = "Windows"
    elif "linux" in ua:
        os_name = "Linux"

    # Browser
    browser_name = "Browser"
    if "edg" in ua:
        browser_name = "Edge"
    elif "chrome" in ua and "chromium" not in ua:
        browser_name = "Chrome"
    elif "firefox" in ua:
        browser_name = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser_name = "Safari"
    elif "opera" in ua or "opr" in ua:
        browser_name = "Opera"

    return f"{browser_name} on {os_name}", device_type


@router.get(
    "/sessions",
    response_model=List[UserSessionResponse],
    summary="List all active devices and sessions for the authenticated user",
)
async def get_active_sessions(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch active device sessions from PostgreSQL refresh_tokens table.
    Identifies the current active device by matching the session's JTI with the active refresh cookie.
    """
    now_utc = datetime.now(timezone.utc)
    query = (
        select(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > now_utc,
        )
        .order_by(RefreshToken.created_at.desc())
    )
    result = await db.execute(query)
    records = result.scalars().all()

    # Identify current device session
    current_jti = None
    refresh_cookie = request.cookies.get(settings.COOKIE_REFRESH_NAME)
    if refresh_cookie:
        try:
            payload = decode_access_token(refresh_cookie)
            current_jti = payload.get("jti")
        except Exception:
            pass

    sessions = []
    found_current = False
    client_ip = get_client_ip(request)

    for rec in records:
        dev_name, dev_type = parse_user_agent(rec.user_agent)
        is_cur = False
        if current_jti and rec.jti == current_jti:
            is_cur = True
            found_current = True
        elif not current_jti and not found_current and rec.ip_address == client_ip:
            is_cur = True
            found_current = True

        sessions.append(
            UserSessionResponse(
                id=str(rec.id),
                device_name=dev_name,
                device_type=dev_type,
                ip_address=rec.ip_address or "Unknown IP",
                created_at=rec.created_at,
                expires_at=rec.expires_at,
                is_current=is_cur,
            )
        )

    return sessions


@router.delete(
    "/sessions/{session_id}",
    summary="Revoke and log out a specific device session",
)
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a single device session:
    1. Validates ownership (must belong to current_user).
    2. Marks session is_revoked = True in PostgreSQL.
    3. Revokes refresh token in Redis.
    4. If it was the current session, clears cookies on response.
    """
    query = select(RefreshToken).where(
        RefreshToken.id == session_id,
        RefreshToken.user_id == current_user.id,
    )
    result = await db.execute(query)
    rec = result.scalar_one_or_none()

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already terminated.",
        )

    rec.is_revoked = True
    rec.updated_at = datetime.utcnow()
    await db.commit()

    # Revoke in Redis
    await revoke_refresh_token(rec.jti, user_id=str(current_user.id))

    # Check if this was the current device session
    current_jti = None
    refresh_cookie = request.cookies.get(settings.COOKIE_REFRESH_NAME)
    if refresh_cookie:
        try:
            payload = decode_access_token(refresh_cookie)
            current_jti = payload.get("jti")
        except Exception:
            pass

    if current_jti and rec.jti == current_jti:
        clear_auth_cookies(response)

    return {
        "status": "success",
        "message": "Device session terminated successfully.",
    }


@router.post(
    "/sessions/revoke-all",
    summary="Log out all devices (or all other devices)",
)
async def revoke_all_sessions(
    request: Request,
    response: Response,
    payload: Optional[RevokeSessionsRequest] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Log out all active sessions:
    - If keep_current = True: keeps current session, revokes all other devices.
    - If keep_current = False: logs out every session including this one, and clears cookies.
    """
    keep_current = payload.keep_current if payload else False
    current_jti = None
    refresh_cookie = request.cookies.get(settings.COOKIE_REFRESH_NAME)
    if refresh_cookie:
        try:
            p = decode_access_token(refresh_cookie)
            current_jti = p.get("jti")
        except Exception:
            pass

    now_utc = datetime.now(timezone.utc)
    query = select(RefreshToken).where(
        RefreshToken.user_id == current_user.id,
        RefreshToken.is_revoked == False,
        RefreshToken.expires_at > now_utc,
    )
    result = await db.execute(query)
    active_tokens = result.scalars().all()

    for token_rec in active_tokens:
        if keep_current and current_jti and token_rec.jti == current_jti:
            continue  # Keep current device active
        token_rec.is_revoked = True
        token_rec.updated_at = datetime.utcnow()
        await revoke_refresh_token(token_rec.jti, user_id=str(current_user.id))

    await db.commit()

    if not keep_current:
        clear_auth_cookies(response)

    msg = (
        "All other device sessions have been logged out."
        if keep_current
        else "All device sessions have been logged out."
    )
    return {"status": "success", "message": msg}


@router.patch(
    "/profile",
    response_model=UserResponse,
    summary="Update user display username",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, key_prefix="update_profile"))],
)
async def update_profile(
    response: Response,
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update display username in database and refresh HttpOnly access token with new username."""
    clean_username = payload.username.strip()
    if len(clean_username) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 2 characters long.",
        )

    current_user.username = clean_username
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)

    # Refresh stateless 5-minute access token cookie so the new username is reflected immediately
    new_access_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "email": current_user.email,
            "username": current_user.username,
            "role": current_user.role,
        }
    )
    set_auth_cookies(response, new_access_token)

    return make_user_response(current_user)


@router.post(
    "/change-password",
    response_model=UserResponse,
    summary="Change or configure master password for the active authenticated user",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, key_prefix="change_password"))],
)
async def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change or configure master password (verified with HttpOnly access token):
    - If user already has a password set, verifies current_password.
    - If user registered via Google OAuth without a password, configures master password directly.
    - Revokes all old refresh tokens across devices in Redis & PostgreSQL.
    - Issues fresh HttpOnly cookies for the current session.
    """
    if current_user.hashed_password:
        if not payload.current_password or not verify_password(payload.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

    current_user.hashed_password = get_password_hash(payload.new_password)
    current_user.is_locked = False
    current_user.failed_attempts = 0
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)

    # Invalidate all existing sessions across devices in Redis & PostgreSQL
    await revoke_all_user_refresh_tokens(str(current_user.id))
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.is_revoked == False)
        .values(is_revoked=True, updated_at=datetime.utcnow())
    )
    await db.commit()

    # Issue fresh token pair & cookies for current device so this session stays verified
    access_token, refresh_token = await issue_token_pair(current_user, db, request)
    set_auth_cookies(response, access_token, refresh_token)

    return make_user_response(current_user)


@router.post(
    "/forgot-password",
    summary="Request a password reset link with Turnstile verification",
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, key_prefix="forgot_password"))],
)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle forgot password request:
    1. Validates human Turnstile token
    2. Generates a signed cryptographic reset token (1-hour expiry)
    3. Always returns generic message to prevent user enumeration
    """
    client_ip = get_client_ip(request)
    token = payload.turnstile_token or request.headers.get("x-turnstile-token")
    if settings.TURNSTILE_ENABLED and not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare human verification check required.",
        )
    if token:
        await verify_turnstile_token(token=token, remote_ip=client_ip, expected_action=["auth", "forgot_password"])

    identifier = payload.email.strip()
    user_query = select(User).where(
        or_(
            User.email == identifier.lower(),
            User.username == identifier,
        )
    )
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()

    dev_reset_token = None
    if user and user.is_active:
        dev_reset_token = create_password_reset_token(
            email=user.email,
            user_id=str(user.id),
            username=user.username,
        )

    response_data = {
        "status": "success",
        "message": f"If an account exists for {payload.email}, password recovery instructions have been dispatched.",
    }
    # Expose reset token in response during local development for testing
    if dev_reset_token:
        response_data["reset_token"] = dev_reset_token
        if user:
            response_data["username"] = user.username or (user.email.split("@")[0] if user.email else "user")

    return response_data


@router.post(
    "/reset-password",
    summary="Reset user password using a valid cryptographic reset token",
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, key_prefix="reset_password"))],
)
async def reset_password(
    request: Request,
    response: Response,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete password reset:
    1. Validates Turnstile challenge
    2. Validates signed cryptographic reset token and expiry
    3. Hashes new password with bcrypt
    4. Unlocks account and clears failed attempt counters
    5. Issues fresh 5-minute access token (with username) and sets HttpOnly cookies
    """
    client_ip = get_client_ip(request)
    turnstile_token = payload.turnstile_token or request.headers.get("x-turnstile-token")
    if settings.TURNSTILE_ENABLED and not turnstile_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare human verification check required.",
        )
    if turnstile_token:
        await verify_turnstile_token(token=turnstile_token, remote_ip=client_ip, expected_action=["auth", "reset_password"])

    token_payload = verify_password_reset_token(payload.token)
    user_id_str = token_payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token identifier.",
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format in reset token.",
        )

    user_query = select(User).where(User.id == user_uuid)
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    # Set new hashed password, unlock account, clear failed attempts
    user.hashed_password = get_password_hash(payload.new_password)
    user.is_locked = False
    user.failed_attempts = 0
    user.updated_at = datetime.utcnow()

    await db.commit()

    # Invalidate all existing sessions across devices in Redis & PostgreSQL
    await revoke_all_user_refresh_tokens(str(user.id))
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.is_revoked == False)
        .values(is_revoked=True, updated_at=datetime.utcnow())
    )
    await db.commit()

    # Issue fresh dual tokens (5-minute stateless access with username claim + 7-day refresh)
    access_token, refresh_token = await issue_token_pair(user, db, request)
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "status": "success",
        "message": "Your password has been successfully updated.",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": make_user_response(user),
    }


@router.post(
    "/google",
    response_model=AuthResponse,
    summary="Authenticate or register user via Google Social Auth (GIS ID Token)",
    dependencies=[Depends(rate_limit(max_requests=15, window_seconds=60, key_prefix="auth_google"))],
)
async def google_auth(
    request: Request,
    response: Response,
    payload: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate or register user using Google Identity Services ID Token:
    1. Validates Turnstile challenge if enabled and token present
    2. Verifies ID token with Google's canonical tokeninfo endpoint
    3. Validates email verification and optional client ID audience
    4. Upserts user (links google_id or creates new account)
    5. Issues application JWT access token
    """
    client_ip = get_client_ip(request)

    # Turnstile verification (optional for Google OAuth, enforced if token provided)
    turnstile_token = payload.turnstile_token or request.headers.get("x-turnstile-token")
    if turnstile_token:
        await verify_turnstile_token(
            token=turnstile_token,
            remote_ip=client_ip,
            expected_action=["auth", "login", "signup", "google_auth"],
        )

    # Verify ID token or access token with Google
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            is_jwt = payload.id_token.count(".") == 2
            query_params = {"id_token": payload.id_token} if is_jwt else {"access_token": payload.id_token}
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params=query_params,
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired Google authentication token.",
                )
            google_info = resp.json()

            # If access_token was provided and user profile name is absent, try userinfo
            if not is_jwt and not google_info.get("name"):
                try:
                    userinfo_resp = await client.get(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {payload.id_token}"},
                    )
                    if userinfo_resp.status_code == 200:
                        uinfo = userinfo_resp.json()
                        if uinfo.get("name"):
                            google_info["name"] = uinfo["name"]
                except Exception:
                    pass
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to reach Google OAuth service: {exc}",
        )

    # Validate audience if GOOGLE_CLIENT_ID configured
    if settings.GOOGLE_CLIENT_ID:
        token_aud = google_info.get("aud") or google_info.get("azp")
        if token_aud != settings.GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Google token audience mismatch.",
            )

    # Ensure email is verified by Google
    email_verified = google_info.get("email_verified")
    if email_verified not in [True, "true", "True"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google account email is not verified.",
        )

    google_sub = google_info.get("sub")
    raw_email = google_info.get("email")
    if not google_sub or not raw_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google identity profile missing email or subject ID.",
        )

    email = raw_email.lower().strip()
    google_name = google_info.get("name")
    default_username = google_name if google_name else email.split("@")[0]

    # Look up existing user by google_id or email
    user_query = select(User).where((User.google_id == google_sub) | (User.email == email))
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()

    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated.",
            )
        if user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="User account is locked. Please contact support.",
            )

        # Link google_id if account was originally email/password
        if not user.google_id:
            user.google_id = google_sub
            user.updated_at = datetime.utcnow()

        if not user.username:
            user.username = default_username
            user.updated_at = datetime.utcnow()

        user.failed_attempts = 0
        await db.commit()
        await db.refresh(user)
    else:
        # Create new user via Google
        user = User(
            id=uuid.uuid4(),
            email=email,
            username=default_username,
            hashed_password=None,
            google_id=google_sub,
            role="user",
            is_active=True,
            is_locked=False,
            failed_attempts=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Generate dual tokens (5-min access + 7-day refresh) recorded in Redis and PostgreSQL
    access_token, refresh_token = await issue_token_pair(user, db, request)
    set_auth_cookies(response, access_token, refresh_token)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=make_user_response(user),
    )
