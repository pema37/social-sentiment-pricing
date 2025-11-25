# backend/schemas/auth.py

from pydantic import BaseModel, EmailStr
from typing import Optional


# -----------------------------
# AUTH: REGISTER / LOGIN
# -----------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str | None = None
    role: str

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# -----------------------------
# PASSWORD RESET
# -----------------------------

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
