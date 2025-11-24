# backend/api/v1/routes/auth.py

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    create_reset_token,
    decode_reset_token,
    get_password_hash,
)
from backend.db.session import get_session
from backend.models import User
from backend.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ───────────────────── Role helper ───────────────────── #

def require_role(required_role: str) -> Callable[[User], User]:
    """Restrict access based on user.role."""
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role != required_role:
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
def register(
    payload: RegisterRequest,
    session: Session = Depends(get_session),
):
    """Create a new user account."""
    email = payload.email.lower()

    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists",
        )

    user = User(
        email=email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
):
    """Login and receive a JWT token."""
    email = payload.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
    })

    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def read_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's info."""
    return current_user


@router.get("/user/data")
def get_user_data(current_user: User = Depends(require_role("USER"))):
    return {"message": f"Hello {current_user.email}! You have USER access."}


@router.get("/admin/data")
def get_admin_data(current_user: User = Depends(require_role("ADMIN"))):
    return {"message": f"Hello {current_user.email}! You have ADMIN access."}


# ───────────────────────── PASSWORD RESET ───────────────────────── #

@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    session: Session = Depends(get_session),
):
    """Send a password reset token (email not revealed)."""
    email = payload.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()

    # Always return success — do not reveal if the account exists
    if user:
        token = create_reset_token(user.id)
        print("===== PASSWORD RESET TOKEN =====")
        print(token)
        print("================================")

    return {"detail": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    session: Session = Depends(get_session),
):
    """Reset password using a valid reset token."""
    user_id = decode_reset_token(payload.token)

    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token",
        )

    user.hashed_password = get_password_hash(payload.new_password)
    session.add(user)
    session.commit()

    return {"detail": "Password reset successful"}
