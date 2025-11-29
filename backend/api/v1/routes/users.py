# backend/api/v1/routes/users.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.models.user import User
from backend.schemas.user import UserRead, UserUpdateMe
from backend.core.security import get_current_user, get_password_hash
from backend.core.deps import require_admin


router = APIRouter(prefix="/users", tags=["Users"])


# ============================
# GET /users/me
# ============================
@router.get("/me", response_model=UserRead)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Return the currently authenticated user's profile.
    """
    return current_user


# ============================
# PATCH /users/me
# ============================
@router.patch("/me", response_model=UserRead)
def update_current_user(
    payload: UserUpdateMe,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Update current user's profile.

    - username (must be unique)
    - email (must be unique)
    - full_name
    - password (will be hashed)
    """

    # 1) Username uniqueness check
    if payload.username and payload.username != current_user.username:
        existing = db.query(User).filter(User.username == payload.username).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        current_user.username = payload.username

    # 2) Email uniqueness check
    if payload.email and payload.email != current_user.email:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        current_user.email = payload.email

    # 3) Full name
    if payload.full_name is not None:
        current_user.full_name = payload.full_name

    # 4) Password (hash it before saving)
    if payload.password:
        current_user.hashed_password = get_password_hash(payload.password)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return current_user


# ============================
# DELETE /users/me
# ============================
@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Delete the currently authenticated user.

    NOTE: This is a hard delete. In a real product you might want a soft delete.
    """
    db.delete(current_user)
    db.commit()
    return


# ============================
# GET /users  (admin only)
# ============================
@router.get("/", response_model=List[UserRead])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),  # ADMIN ROLE CHECK
) -> List[User]:
    users = db.query(User).offset(skip).limit(limit).all()
    return users

