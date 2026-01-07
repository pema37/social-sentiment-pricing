# backend/schemas/auth.py

"""
Auth Schemas.

PATCHED (2025-01-07): Added RefreshRequest and refresh_token to TokenResponse.
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None 


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """NEW: Refresh token request payload."""
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    username: str | None = None
    full_name: str | None = None 
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None  # NEW: Optional for backwards compatibility
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


