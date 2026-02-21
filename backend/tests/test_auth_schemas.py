"""
Test Suite: backend/schemas/auth.py
Covers: RegisterRequest, LoginRequest, RefreshRequest, UserResponse,
        TokenResponse, ForgotPasswordRequest, ResetPasswordRequest.

Place this file at: backend/tests/test_auth_schemas.py
Run with: pytest backend/tests/test_auth_schemas.py -v
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    UserResponse,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)


# =====================================================================
# RegisterRequest
# =====================================================================

class TestRegisterRequest:

    def test_valid_minimal(self):
        """Email + password is enough (full_name is optional)."""
        req = RegisterRequest(email="user@example.com", password="secret123")
        assert req.email == "user@example.com"
        assert req.password == "secret123"
        assert req.full_name is None

    def test_valid_with_full_name(self):
        req = RegisterRequest(
            email="user@example.com",
            password="secret123",
            full_name="Shaw Test",
        )
        assert req.full_name == "Shaw Test"

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError) as exc:
            RegisterRequest(password="secret123")
        assert "email" in str(exc.value).lower()

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError) as exc:
            RegisterRequest(email="user@example.com")
        assert "password" in str(exc.value).lower()

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="not-an-email", password="secret123")

    def test_empty_email_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="", password="secret123")

    def test_empty_password_accepted(self):
        """Pydantic won't reject empty string — that's business logic."""
        req = RegisterRequest(email="user@example.com", password="")
        assert req.password == ""

    def test_email_normalized(self):
        """Pydantic EmailStr lowercases domain."""
        req = RegisterRequest(email="User@EXAMPLE.COM", password="pw")
        assert "example.com" in req.email


# =====================================================================
# LoginRequest
# =====================================================================

class TestLoginRequest:

    def test_valid(self):
        req = LoginRequest(email="user@example.com", password="secret")
        assert req.email == "user@example.com"
        assert req.password == "secret"

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(password="secret")

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="user@example.com")

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="bad", password="secret")

    def test_both_missing_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest()


# =====================================================================
# RefreshRequest
# =====================================================================

class TestRefreshRequest:

    def test_valid(self):
        req = RefreshRequest(refresh_token="eyJhbGciOiJIUzI1NiJ9.test")
        assert req.refresh_token == "eyJhbGciOiJIUzI1NiJ9.test"

    def test_missing_token_raises(self):
        with pytest.raises(ValidationError):
            RefreshRequest()

    def test_empty_string_accepted(self):
        """Empty string passes Pydantic — validation is in the endpoint."""
        req = RefreshRequest(refresh_token="")
        assert req.refresh_token == ""


# =====================================================================
# TokenResponse
# =====================================================================

class TestTokenResponse:

    def test_valid_minimal(self):
        """Only access_token required; refresh_token optional."""
        resp = TokenResponse(access_token="abc123")
        assert resp.access_token == "abc123"
        assert resp.refresh_token is None
        assert resp.token_type == "bearer"

    def test_valid_with_refresh(self):
        resp = TokenResponse(access_token="abc", refresh_token="def")
        assert resp.refresh_token == "def"

    def test_default_token_type(self):
        resp = TokenResponse(access_token="abc")
        assert resp.token_type == "bearer"

    def test_custom_token_type(self):
        resp = TokenResponse(access_token="abc", token_type="custom")
        assert resp.token_type == "custom"

    def test_missing_access_token_raises(self):
        with pytest.raises(ValidationError):
            TokenResponse()


# =====================================================================
# UserResponse
# =====================================================================

class TestUserResponse:

    @pytest.fixture
    def valid_user_data(self):
        return {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "role": "USER",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }

    def test_valid_minimal(self, valid_user_data):
        resp = UserResponse(**valid_user_data)
        assert resp.email == "test@example.com"
        assert resp.role == "USER"
        assert resp.is_active is True
        assert resp.username is None
        assert resp.full_name is None
        assert resp.updated_at is None

    def test_valid_full(self, valid_user_data):
        data = {
            **valid_user_data,
            "username": "testuser",
            "full_name": "Test User",
            "updated_at": datetime.now(timezone.utc),
        }
        resp = UserResponse(**data)
        assert resp.username == "testuser"
        assert resp.full_name == "Test User"
        assert resp.updated_at is not None

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            UserResponse(
                email="t@t.com", role="USER",
                is_active=True, created_at=datetime.now(timezone.utc),
            )

    def test_missing_email_raises(self, valid_user_data):
        del valid_user_data["email"]
        with pytest.raises(ValidationError):
            UserResponse(**valid_user_data)

    def test_invalid_email_raises(self, valid_user_data):
        valid_user_data["email"] = "not-email"
        with pytest.raises(ValidationError):
            UserResponse(**valid_user_data)

    def test_missing_role_raises(self, valid_user_data):
        del valid_user_data["role"]
        with pytest.raises(ValidationError):
            UserResponse(**valid_user_data)

    def test_missing_created_at_raises(self, valid_user_data):
        del valid_user_data["created_at"]
        with pytest.raises(ValidationError):
            UserResponse(**valid_user_data)

    def test_uuid_as_string_accepted(self):
        """UUID can be passed as string — Pydantic coerces it."""
        resp = UserResponse(
            id="12345678-1234-5678-1234-567812345678",
            email="t@t.com", role="USER",
            is_active=True, created_at=datetime.now(timezone.utc),
        )
        assert isinstance(resp.id, uuid.UUID)


# =====================================================================
# ForgotPasswordRequest
# =====================================================================

class TestForgotPasswordRequest:

    def test_valid(self):
        req = ForgotPasswordRequest(email="user@example.com")
        assert req.email == "user@example.com"

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            ForgotPasswordRequest()

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email="nope")


# =====================================================================
# ResetPasswordRequest
# =====================================================================

class TestResetPasswordRequest:

    def test_valid(self):
        req = ResetPasswordRequest(token="abc123", new_password="newpass")
        assert req.token == "abc123"
        assert req.new_password == "newpass"

    def test_missing_token_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(new_password="newpass")

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="abc123")

    def test_both_missing_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest()


            