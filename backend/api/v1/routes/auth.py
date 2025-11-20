# ======================================================
# Authentication and Authorization Routes
# Handles registration, login, JWT token creation,
# role-based access control, and retrieving the current user.
# All logic is fully commented for clarity.
# ======================================================

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from backend.db.session import get_session
from backend.models.user import User
from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

# Router instance for all "/auth" related endpoints
router = APIRouter()

# OAuth2 password flow configuration
# FastAPI will call the login endpoint defined below for token retrieval
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ------------------------------------------------------
# Pydantic Schemas (Validation Models)
# ------------------------------------------------------

class UserCreate(BaseModel):
    """
    Schema for user registration requests.
    """
    username: str
    email: EmailStr
    password: str
    role: str = "USER"  # Default role is USER


class UserRead(BaseModel):
    """
    Schema returned when user data is fetched.
    Ensures sensitive data (like password_hash) is never returned.
    """
    id: int
    username: str
    email: EmailStr
    role: str


class Token(BaseModel):
    """
    Schema returned after successful login.
    """
    access_token: str
    token_type: str = "bearer"


# ------------------------------------------------------
# Utility Dependencies
# ------------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """
    Decodes the JWT token and retrieves the corresponding user from the database.
    Ensures the token is valid and the user exists.
    """

    # Decode JWT payload
    payload = decode_access_token(token)

    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # The "sub" field stores the user's email
    email = payload["sub"]

    # Fetch the user by email
    user = session.exec(select(User).where(User.email == email)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def require_role(required_role: str):
    """
    Dependency generator for role-based authorization.
    Ensures the endpoint caller has the required user role.
    """

    def role_checker(user: User = Depends(get_current_user)) -> User:
        # Reject access if roles don't match
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )
        return user

    return role_checker


# ------------------------------------------------------
# Registration Route
# ------------------------------------------------------

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    session: Session = Depends(get_session),
):
    """
    Creates a new user.
    Validates unique email, hashes password, and stores user in the DB.
    """

    # Check if email already exists
    existing = session.exec(
        select(User).where(User.email == user_in.email.lower())
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists",
        )

    # Create new user object
    user = User(
        username=user_in.username,
        email=user_in.email.lower(),
        password_hash=hash_password(user_in.password),
        role=user_in.role,
    )

    # Save to database
    session.add(user)
    session.commit()
    session.refresh(user)

    return user


# ------------------------------------------------------
# Login Route
# ------------------------------------------------------

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """
    Authenticates a user using email + password.
    Returns a signed JWT token if credentials are correct.
    """

    # OAuth2PasswordRequestForm uses "username" field → we treat it as email
    email = form_data.username.lower()

    # Fetch user by email
    user = session.exec(select(User).where(User.email == email)).first()

    # Validate password
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Create a JWT with user's email and role
    token = create_access_token({"sub": user.email, "role": user.role})

    return {"access_token": token, "token_type": "bearer"}


# ------------------------------------------------------
# Profile Route
# ------------------------------------------------------

@router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)):
    """
    Returns information about the authenticated user.
    """
    return current_user


# ------------------------------------------------------
# Role-Based Protected Routes
# ------------------------------------------------------

@router.get("/user/data")
def get_user_data(current_user: User = Depends(require_role("USER"))):
    """
    Accessible only by users with the USER role.
    """
    return {"message": f"Hello {current_user.email}! You have USER access."}


@router.get("/admin/data")
def get_admin_data(current_user: User = Depends(require_role("ADMIN"))):
    """
    Accessible only by users with the ADMIN role.
    """
    return {"message": f"Hello {current_user.email}! You have ADMIN access."}
