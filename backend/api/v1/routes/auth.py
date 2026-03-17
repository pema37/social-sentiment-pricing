# backend/api/v1/routes/auth.py

"""
Authentication Routes.

PATCHED (2025-01-07): Added refresh token support to prevent session timeouts.
- Login now returns both access_token and refresh_token
- New /auth/refresh endpoint to get new access token using refresh token
"""

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.rate_limit import AUTH_RATE_LIMIT, PASSWORD_RESET_RATE_LIMIT, REGISTER_RATE_LIMIT, limiter
from core.security import (
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
    session: AsyncSession = Depends(get_session),
):
    """Login and receive JWT tokens (JSON body)."""
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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login/oauth", response_model=TokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def login_oauth(
    request: Request,
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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def refresh_tokens(
    request: Request,
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Get new access token using a valid refresh token.

    This endpoint allows the frontend to silently refresh the session
    without forcing the user to re-login.
    """
    # Decode the refresh token
    token_payload = decode_refresh_token(payload.refresh_token)

    if token_payload is None:
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

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


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
        return {"message": "If that email exists, a reset link has been sent"}

    if not user.is_active:
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

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    user.hashed_password = hash_password(payload.new_password)
    session.add(user)
    await session.commit()

    return {"message": "Password reset successfully"}
