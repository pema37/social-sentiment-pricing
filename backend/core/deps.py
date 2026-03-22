# backend/core/deps.py

"""
FastAPI Dependencies

Common dependencies for authentication and database access.

FIXED (2026-03-21): BUG-001 — get_current_user now reads JWT from httpOnly
cookie first, falling back to Authorization header. This supports the
migration from localStorage to httpOnly cookies on the frontend.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import decode_access_token
from db.session import get_session
from models.user import User

# OAuth2 scheme for token extraction — auto_error=False so we can fall back
# to the httpOnly cookie when no Authorization header is present.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/oauth", auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    Get the current authenticated user from JWT token.

    Token resolution order:
      1. httpOnly cookie ``ssp_access_token`` (set by login/refresh endpoints)
      2. Authorization: Bearer header (for API clients / Swagger UI)

    Raises 401 if no valid token is found or user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Prefer httpOnly cookie, fall back to Authorization header
    jwt_token = request.cookies.get("ssp_access_token") or token
    if not jwt_token:
        raise credentials_exception

    # Decode the token
    payload = decode_access_token(jwt_token)
    if payload is None:
        raise credentials_exception

    # Extract user ID from token
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    # Fetch user from database (async)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that ensures the current user has ADMIN role.
    Use in routes that should be admin-only.
    """
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user
