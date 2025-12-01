# backend/core/deps.py

"""
FastAPI Dependencies

Common dependencies for authentication and database access.
"""

from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from backend.db.session import engine, get_session
from backend.core.security import decode_access_token
from backend.models.user import User

# OAuth2 scheme for token extraction - points to OAuth form endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/oauth")


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.
    Yields a SQLModel session and ensures it's closed after use.
    """
    with Session(engine) as session:
        yield session


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.
    Raises 401 if token is invalid or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode the token
    payload = decode_access_token(token)
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
    
    # Fetch user from database
    user = db.exec(select(User).where(User.id == user_id)).first()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    return user


def require_admin(
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

