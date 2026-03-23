# backend/api/v1/routes/users.py

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.v1.routes.auth import require_role
from core.deps import get_current_user
from core.rate_limit import AUTH_RATE_LIMIT, WRITE_RATE_LIMIT, limiter
from core.security import hash_password, verify_password
from db.session import get_session
from models import User
from schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/users", tags=["users"])


# ───────────────────── Schemas ───────────────────── #


class UserUpdateRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    full_name: str | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class WalletUpdateRequest(BaseModel):
    eth_wallet_address: str | None = None
    bsv_wallet_address: str | None = None

    @field_validator("eth_wallet_address")
    @classmethod
    def validate_eth_address(cls, v):
        if v is None:
            return v
        # Ethereum addresses: 0x followed by 40 hex characters
        if not re.match(r"^0x[a-fA-F0-9]{40}$", v):
            raise ValueError("Invalid Ethereum address format")
        return v.lower()  # Normalize to lowercase

    @field_validator("bsv_wallet_address")
    @classmethod
    def validate_bsv_address(cls, v):
        if v is None:
            return v
        # BSV addresses: typically start with 1 or 3, or PayMail format
        # Allow PayMail (email-like) or standard addresses
        if "@" in v:
            # PayMail format (e.g., $pema12@handcash.io)
            return v
        if not re.match(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$", v):
            raise ValueError("Invalid BSV address format")
        return v


class UserDetailResponse(BaseModel):
    id: UUID
    email: str
    username: str | None
    full_name: str | None
    role: str
    is_active: bool
    eth_wallet_address: str | None
    bsv_wallet_address: str | None

    class Config:
        from_attributes = True


class WalletResponse(BaseModel):
    eth_wallet_address: str | None
    bsv_wallet_address: str | None


# ───────────────────── User Self-Management ───────────────────── #


@router.get("/me", response_model=UserDetailResponse)
async def get_my_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get current user's profile."""
    return current_user


@router.patch("/me", response_model=UserDetailResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def update_my_profile(
    request: Request,
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update current user's profile (username, email)."""

    if payload.email is not None:
        email = payload.email.lower()
        stmt = select(User).where(User.email == email, User.id != current_user.id)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )
        current_user.email = email

    if payload.username is not None:
        stmt = select(User).where(User.username == payload.username, User.id != current_user.id)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already in use",
            )
        current_user.username = payload.username

    if payload.full_name is not None:
        current_user.full_name = payload.full_name

    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    return current_user


@router.put("/me/wallet", response_model=WalletResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def update_my_wallet(
    request: Request,
    payload: WalletUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update current user's wallet addresses (ETH and/or BSV)."""

    if payload.eth_wallet_address is not None:
        current_user.eth_wallet_address = payload.eth_wallet_address

    if payload.bsv_wallet_address is not None:
        current_user.bsv_wallet_address = payload.bsv_wallet_address

    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    return WalletResponse(
        eth_wallet_address=current_user.eth_wallet_address,
        bsv_wallet_address=current_user.bsv_wallet_address,
    )


@router.get("/me/wallet", response_model=WalletResponse)
async def get_my_wallet(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get current user's wallet addresses."""
    return WalletResponse(
        eth_wallet_address=current_user.eth_wallet_address,
        bsv_wallet_address=current_user.bsv_wallet_address,
    )


@router.post("/me/change-password", status_code=status.HTTP_200_OK)
@limiter.limit(AUTH_RATE_LIMIT)
async def change_my_password(
    request: Request,
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Change current user's password."""

    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    session.add(current_user)
    await session.commit()

    return {"message": "Password changed successfully"}


@router.delete("/me", status_code=status.HTTP_200_OK)
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_my_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete current user's account (soft delete - deactivates)."""
    current_user.is_active = False
    session.add(current_user)
    await session.commit()

    return {"message": "Account deactivated successfully"}


# ───────────────────── Admin Endpoints ───────────────────── #


@router.get("/", response_model=PaginatedResponse[UserDetailResponse])
async def list_all_users(
    request: Request,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    """List all users (Admin only)."""
    count_query = select(func.count()).select_from(User)
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    stmt = select(User).offset(pagination.offset).limit(pagination.page_size)
    result = await session.execute(stmt)
    users = list(result.scalars().all())

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=users,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user_by_id(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific user by ID (Admin only)."""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.patch("/{user_id}/deactivate", status_code=status.HTTP_200_OK)
@limiter.limit(WRITE_RATE_LIMIT)
async def deactivate_user(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    """Deactivate a user account (Admin only)."""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    user.is_active = False
    session.add(user)
    await session.commit()

    return {"message": f"User {user.email} deactivated"}


@router.patch("/{user_id}/activate", status_code=status.HTTP_200_OK)
@limiter.limit(WRITE_RATE_LIMIT)
async def activate_user(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    """Reactivate a user account (Admin only)."""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_active = True
    session.add(user)
    await session.commit()

    return {"message": f"User {user.email} activated"}
