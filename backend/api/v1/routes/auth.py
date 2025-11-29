# backend/api/v1/routes/auth.py

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select

from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from backend.db.session import get_session
from backend.models import User
from backend.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/oauth")


# ───────────────────── Current user helpers ───────────────────── #

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
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

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


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
    """Login and receive a JWT token (JSON body)."""
    email = payload.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    return TokenResponse(access_token=token)


@router.post("/login/oauth", response_model=TokenResponse)
def login_oauth(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Login via OAuth2 form (for Swagger UI)."""
    email = form_data.username.lower()
    user = session.exec(select(User).where(User.email == email)).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role
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

