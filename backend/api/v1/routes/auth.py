# backend/api/v1/routes/auth.py

"""
Authentication Routes.

PATCHED (2025-01-07): Added refresh token support to prevent session timeouts.
- Login now returns both access_token and refresh_token
- New /auth/refresh endpoint to get new access token using refresh token
"""

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import settings
from core.rate_limit import AUTH_RATE_LIMIT, PASSWORD_RESET_RATE_LIMIT, REGISTER_RATE_LIMIT, limiter
from jose import JWTError, jwt

from core.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_access_token,
    decode_refresh_token,
    decode_reset_token,
    hash_password,
    verify_password,
)
from db.session import get_session
from models import User
from schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/oauth")

# Cookie settings for httpOnly JWT storage (BUG-001 fix)
_COOKIE_SECURE = settings.ENVIRONMENT != "development"
_COOKIE_SAMESITE: str = "none" if _COOKIE_SECURE else "lax"
_ACCESS_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
_REFRESH_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set httpOnly cookies for both tokens on the response."""
    response.set_cookie(
        key="ssp_access_token",
        value=access_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        max_age=_ACCESS_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="ssp_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        max_age=_REFRESH_MAX_AGE,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Delete httpOnly auth cookies."""
    response.delete_cookie("ssp_access_token", path="/")
    response.delete_cookie("ssp_refresh_token", path="/")


# ───────────────────── Role hierarchy ───────────────────── #

ROLE_HIERARCHY = {
    "ADMIN": 100,
    "USER": 10,
}


# ───────────────────── Current user helpers ───────────────────── #


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Extract user from JWT."""
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload["sub"]
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
        )

    user = await session.get(User, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def require_role(min_role: str) -> Callable[[User], User]:
    """Restrict access based on role hierarchy. ADMIN can access everything."""

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(user.role, 0)
        required_level = ROLE_HIERARCHY.get(min_role, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )
        return user

    return role_checker


# ───────────────────────────── Auth Endpoints ───────────────────────────── #


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(REGISTER_RATE_LIMIT)
async def register(
    request: Request,
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new user account."""
    email = payload.email.lower()

    result = await session.execute(select(User).where(User.email == email))
    existing = result.scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists",
        )

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Login and receive JWT tokens (JSON body + httpOnly cookies)."""
    email = payload.email.lower()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    token_data = {
        "sub": str(user.id),
        "role": user.role,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login/oauth", response_model=TokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def login_oauth(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """Login via OAuth2 form (for Swagger UI)."""
    email = form_data.username.lower()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    token_data = {
        "sub": str(user.id),
        "role": user.role,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def refresh_tokens(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
):
    """
    Get new access token using a valid refresh token.

    Reads the refresh token from:
      1. httpOnly cookie ``ssp_refresh_token`` (preferred — browser clients)
      2. JSON body ``refresh_token`` field (fallback — API clients)
    """
    # Prefer httpOnly cookie, fall back to request body
    raw_token = request.cookies.get("ssp_refresh_token")
    if not raw_token and payload and payload.refresh_token:
        raw_token = payload.refresh_token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    # Decode the refresh token
    token_payload = decode_refresh_token(raw_token)

    if token_payload is None:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
        )

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )

    # Verify user still exists and is active
    user = await session.get(User, user_uuid)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Create new tokens
    token_data = {
        "sub": str(user.id),
        "role": user.role,
    }

    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    _set_auth_cookies(response, new_access_token, new_refresh_token)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response):
    """Clear httpOnly auth cookies."""
    _clear_auth_cookies(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def read_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's info."""
    return current_user


@router.get("/user/data")
async def get_user_data(current_user: User = Depends(require_role("USER"))):
    """Example endpoint requiring USER role (or higher)."""
    return {"message": f"Hello {current_user.email}! You have USER access."}


@router.get("/admin/data")
async def get_admin_data(current_user: User = Depends(require_role("ADMIN"))):
    """Example endpoint requiring ADMIN role."""
    return {"message": f"Hello {current_user.email}! You have ADMIN access."}


# ───────────────────────────── Password Reset ───────────────────────────── #


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit(PASSWORD_RESET_RATE_LIMIT)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Request a password reset token.
    In production, this would send an email. For dev, it prints the token.
    """
    email = payload.email.lower()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if not user:
        create_reset_token("00000000-0000-0000-0000-000000000000")
        return {"message": "If that email exists, a reset link has been sent"}

    if not user.is_active:
        create_reset_token("00000000-0000-0000-0000-000000000000")
        return {"message": "If that email exists, a reset link has been sent"}

    reset_token = create_reset_token(str(user.id))

    # TODO: In production, send this via email
    print(f"\n{'=' * 50}")
    print(f"PASSWORD RESET TOKEN FOR: {email}")
    print(f"Token: {reset_token}")
    print(f"{'=' * 50}\n")

    return {"message": "If that email exists, a reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit(AUTH_RATE_LIMIT)
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """Reset password using a valid reset token."""
    user_id = decode_reset_token(payload.token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token format",
        )

    user = await session.get(User, user_uuid)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Reject reused tokens: if password was changed after token was issued,
    # the token has already been consumed (BUG-126)
    try:
        token_payload = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
        token_iat = token_payload.get("iat", 0)
    except JWTError:
        token_iat = 0
    if user.updated_at and token_iat and user.updated_at.timestamp() > token_iat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    user.hashed_password = hash_password(payload.new_password)
    session.add(user)
    await session.commit()

    return {"message": "Password reset successfully"}
