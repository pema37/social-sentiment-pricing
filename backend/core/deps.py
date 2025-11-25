# backend/core/deps.py

from fastapi import Depends, HTTPException, status

from backend.models.user import User
from backend.core.security import get_current_user


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

