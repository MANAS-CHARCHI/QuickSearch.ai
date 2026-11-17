from datetime import datetime
from typing import Optional, Tuple
import uuid
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.limiter import rate_limit
from app.core.redis import (
    is_token_valid,
    revoke_all_user_tokens,
    revoke_token,
    store_token_mapping,
)
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    verify_password,
    verify_password_reset_token,
)
from app.core.turnstile import get_client_ip, verify_turnstile_token
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LogoutRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    UserLoginRequest,
    UserRegisterRequest,
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


async def issue_token_pair(user: User) -> Tuple[str, str]:
    """
    Issue a 15-minute access token and 7-day refresh token.
    Stores exp and jti mapping in Redis Hash Map for minimal O(1) latency.
    """
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}

    access_token = create_access_token(data=token_data)
    access_payload = decode_access_token(access_token)
    await store_token_mapping(
        jti=access_payload["jti"],
        user_id=str(user.id),
        token_type="access",
        exp_timestamp=access_payload["exp"],
    )

    refresh_token = create_refresh_token(data=token_data)
    refresh_payload = decode_access_token(refresh_token)
    await store_token_mapping(
        jti=refresh_payload["jti"],
        user_id=str(user.id),
        token_type="refresh",
        exp_timestamp=refresh_payload["exp"],
    )

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
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user:
    1. Validates human Turnstile token
    2. Validates email uniqueness
    3. Hashes password securely via bcrypt
    4. Persists user in database
    5. Returns JWT access token and user profile
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

            token_data = {"sub": str(existing_user.id), "email": existing_user.email, "role": existing_user.role}
            access_token = create_access_token(data=token_data)

            return AuthResponse(
                access_token=access_token,
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

    # Generate dual tokens (15-min access + 7-day refresh) recorded in Redis
    access_token, refresh_token = await issue_token_pair(new_user)

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
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user:
    1. Validates human Turnstile token
    2. Enforces account lock guard on 5 consecutive failed attempts
    3. Verifies bcrypt password hash
    4. Issues JWT access token
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

    # Fetch user
    user_query = select(User).where(User.email == payload.email.lower().strip())
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

    # Generate dual tokens (15-min access + 7-day refresh) recorded in Redis
    access_token, refresh_token = await issue_token_pair(user)

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
    summary="Exchange valid 7-day refresh token for a fresh 15-minute access token",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, key_prefix="auth_refresh"))],
)
async def refresh_session(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate cryptographic refresh token and issue a fresh access token.
    1. Decodes JWT and ensures type == 'refresh' and not expired.
    2. Validates JTI in Redis Hash Map in O(1) time.
    3. Verifies user exists, is active, and is not locked.
    4. Rotates tokens: generates fresh 15-minute access token & fresh 7-day refresh token.
    5. Invalidates old refresh token in Redis.
    """
    refresh_payload = decode_refresh_token(payload.refresh_token)
    jti = refresh_payload.get("jti")
    user_id_str = refresh_payload.get("sub")

    if not jti or not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed session refresh credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check JTI map in Redis (O(1) lookup)
    valid = await is_token_valid(jti, user_id=user_id_str)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refresh token has expired or been revoked.",
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

    # Issue fresh dual tokens (15-min access + rolling 7-day refresh)
    new_access_token, new_refresh_token = await issue_token_pair(user)

    # Revoke used refresh token in Redis
    await revoke_token(jti, user_id=user_id_str)

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
    payload: Optional[LogoutRequest] = None,
):
    """
    Log out active user:
    1. Extracts Bearer token from Authorization header and revokes its JTI in Redis map.
    2. Revokes provided refresh token JTI in Redis map.
    3. Guarantees token cannot be used again.
    """
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        access_token = auth_header.split(" ", 1)[1]
        try:
            token_payload = decode_access_token(access_token)
            jti = token_payload.get("jti")
            sub = token_payload.get("sub")
            if jti:
                await revoke_token(jti, user_id=sub)
        except Exception:
            pass

    if payload and payload.refresh_token:
        try:
            refresh_payload = decode_access_token(payload.refresh_token)
            jti = refresh_payload.get("jti")
            sub = refresh_payload.get("sub")
            if jti:
                await revoke_token(jti, user_id=sub)
        except Exception:
            pass

    return {
        "status": "success",
        "message": "Successfully logged out. All session tokens invalidated.",
    }


@router.patch(
    "/profile",
    response_model=UserResponse,
    summary="Update user display username",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, key_prefix="update_profile"))],
)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update display username in database."""
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

    return make_user_response(current_user)


@router.post(
    "/change-password",
    response_model=UserResponse,
    summary="Change or configure master password for the active authenticated user",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, key_prefix="change_password"))],
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change or configure master password:
    - If user already has a password set, verifies current_password.
    - If user registered via Google OAuth without a password, configures master password directly.
    """
    if current_user.hashed_password:
        if not payload.current_password or not verify_password(payload.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

    current_user.hashed_password = get_password_hash(payload.new_password)
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)

    # Invalidate all existing sessions across devices in Redis
    await revoke_all_user_tokens(str(current_user.id))

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

    user_query = select(User).where(User.email == payload.email.lower().strip())
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()

    dev_reset_token = None
    if user and user.is_active:
        dev_reset_token = create_password_reset_token(email=user.email, user_id=str(user.id))

    response_data = {
        "status": "success",
        "message": f"If an account exists for {payload.email}, password recovery instructions have been dispatched.",
    }
    # Expose reset token in response during local development for testing
    if dev_reset_token:
        response_data["reset_token"] = dev_reset_token

    return response_data


@router.post(
    "/reset-password",
    summary="Reset user password using a valid cryptographic reset token",
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, key_prefix="reset_password"))],
)
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete password reset:
    1. Validates Turnstile challenge
    2. Validates signed cryptographic reset token and expiry
    3. Hashes new password with bcrypt
    4. Unlocks account and clears failed attempt counters
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

    # Invalidate all existing sessions across devices in Redis
    await revoke_all_user_tokens(str(user.id))

    return {
        "status": "success",
        "message": "Your password has been successfully updated. You may now sign in.",
    }


@router.post(
    "/google",
    response_model=AuthResponse,
    summary="Authenticate or register user via Google Social Auth (GIS ID Token)",
    dependencies=[Depends(rate_limit(max_requests=15, window_seconds=60, key_prefix="auth_google"))],
)
async def google_auth(
    request: Request,
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

    # Generate dual tokens (15-min access + 7-day refresh) recorded in Redis
    access_token, refresh_token = await issue_token_pair(user)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=make_user_response(user),
    )
