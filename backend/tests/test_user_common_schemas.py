"""
Test Suite: backend/schemas/user.py + backend/schemas/common.py
Covers: UserBase, UserCreate, UserRead, UserUpdateMe,
        PaginatedResponse, PaginationParams.

Place this file at: backend/tests/test_user_common_schemas.py
Run with: pytest backend/tests/test_user_common_schemas.py -v
"""

import pytest
from pydantic import ValidationError

from schemas.common import PaginatedResponse, PaginationParams
from schemas.user import UserBase, UserCreate, UserRead, UserUpdateMe

# =====================================================================
# UserBase
# =====================================================================


class TestUserBase:
    def test_valid_minimal(self):
        u = UserBase(email="test@example.com")
        assert u.email == "test@example.com"
        assert u.username is None
        assert u.is_active is True

    def test_valid_full(self):
        u = UserBase(email="test@example.com", username="shaw", is_active=False)
        assert u.username == "shaw"
        assert u.is_active is False

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            UserBase(email="not-an-email")

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            UserBase()


# =====================================================================
# UserCreate
# =====================================================================


class TestUserCreate:
    def test_valid_minimal(self):
        u = UserCreate(email="test@example.com", password="secret123")
        assert u.email == "test@example.com"
        assert u.password == "secret123"
        assert u.username is None

    def test_valid_with_username(self):
        u = UserCreate(email="test@example.com", password="secret123", username="shaw")
        assert u.username == "shaw"

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            UserCreate(password="secret123")

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com")

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            UserCreate(email="bad", password="secret123")


# =====================================================================
# UserRead
# =====================================================================


class TestUserRead:
    def test_valid(self):
        u = UserRead(
            id=1,
            email="test@example.com",
            username="shaw",
            role="user",
            is_active=True,
        )
        assert u.id == 1
        assert u.role == "user"

    def test_valid_without_username(self):
        u = UserRead(
            id=2,
            email="admin@example.com",
            role="admin",
            is_active=True,
        )
        assert u.username is None

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            UserRead(email="test@example.com", role="user", is_active=True)

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            UserRead(id=1, role="user", is_active=True)

    def test_missing_role_raises(self):
        with pytest.raises(ValidationError):
            UserRead(id=1, email="test@example.com", is_active=True)


# =====================================================================
# UserUpdateMe
# =====================================================================


class TestUserUpdateMe:
    def test_empty_update(self):
        u = UserUpdateMe()
        assert u.username is None
        assert u.email is None
        assert u.full_name is None
        assert u.password is None

    def test_partial_update_username(self):
        u = UserUpdateMe(username="new_name")
        assert u.username == "new_name"
        assert u.email is None

    def test_partial_update_email(self):
        u = UserUpdateMe(email="new@example.com")
        assert u.email == "new@example.com"

    def test_partial_update_password(self):
        u = UserUpdateMe(password="new_password")
        assert u.password == "new_password"

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            UserUpdateMe(email="not-valid")

    def test_full_update(self):
        u = UserUpdateMe(
            username="shaw",
            email="shaw@example.com",
            full_name="Shaw",
            password="newpass",
        )
        assert u.full_name == "Shaw"


# =====================================================================
# PaginatedResponse
# =====================================================================


class TestPaginatedResponse:
    def test_valid_with_strings(self):
        r = PaginatedResponse[str](
            items=["a", "b", "c"],
            total=3,
            page=1,
            page_size=20,
            total_pages=1,
        )
        assert len(r.items) == 3
        assert r.total == 3

    def test_valid_with_dicts(self):
        r = PaginatedResponse[dict](
            items=[{"id": 1}, {"id": 2}],
            total=50,
            page=3,
            page_size=20,
            total_pages=3,
        )
        assert r.page == 3
        assert r.total_pages == 3

    def test_empty_items(self):
        r = PaginatedResponse[str](
            items=[],
            total=0,
            page=1,
            page_size=20,
            total_pages=0,
        )
        assert r.items == []

    def test_missing_total_raises(self):
        with pytest.raises(ValidationError):
            PaginatedResponse[str](
                items=[],
                page=1,
                page_size=20,
                total_pages=0,
            )


# =====================================================================
# PaginationParams
# =====================================================================


class TestPaginationParams:
    """PaginationParams uses FastAPI Query() defaults which only resolve
    inside FastAPI's dependency injection. Tests must pass explicit values."""

    def test_explicit_values(self):
        p = PaginationParams(page=1, page_size=20)
        assert p.page == 1
        assert p.page_size == 20
        assert p.offset == 0

    def test_custom_values(self):
        p = PaginationParams(page=3, page_size=50)
        assert p.page == 3
        assert p.page_size == 50
        assert p.offset == 100  # (3-1)*50

    def test_offset_calculation(self):
        p = PaginationParams(page=5, page_size=10)
        assert p.offset == 40  # (5-1)*10
