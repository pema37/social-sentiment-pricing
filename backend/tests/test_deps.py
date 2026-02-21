"""
Test Suite: backend/core/deps.py
Covers: oauth2_scheme config, get_current_user, require_admin.

NOTE: db/session.py creates async engines at import time, which fails
in test environments without asyncpg. We mock the module in sys.modules
before importing core.deps.

Place at: backend/tests/test_deps.py
Run: pytest backend/tests/test_deps.py -v
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


# =====================================================================
# Import Isolation: mock db.session before importing core.deps
# =====================================================================

# Save originals so we can restore if needed
_original_db_session = sys.modules.get("db.session")

# Create a mock db.session module with a mock get_session
_mock_session_module = MagicMock()
_mock_session_module.get_session = AsyncMock()
sys.modules.setdefault("db.session", _mock_session_module)

# Now safe to import core.deps (it does `from db.session import get_session`)
from core.deps import get_current_user, require_admin, oauth2_scheme  # noqa: E402


# =====================================================================
# Helpers
# =====================================================================

def make_mock_user(user_id=None, is_active=True, role="USER"):
    """Create a mock User object."""
    user = MagicMock()
    user.id = user_id or uuid4()
    user.is_active = is_active
    user.role = role
    user.email = "test@example.com"
    return user


def make_mock_db(user=None):
    """Create a mock AsyncSession that returns the given user."""
    db = AsyncMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.first.return_value = user
    result.scalars.return_value = scalars
    db.execute.return_value = result
    return db


# =====================================================================
# oauth2_scheme
# =====================================================================

class TestOAuth2Scheme:

    def test_token_url(self):
        assert oauth2_scheme.model.flows.password.tokenUrl == "/api/v1/auth/login/oauth"


# =====================================================================
# get_current_user
# =====================================================================

class TestGetCurrentUser:

    @pytest.mark.asyncio
    @patch("core.deps.decode_access_token")
    async def test_valid_token_returns_user(self, mock_decode):
        user_id = uuid4()
        mock_decode.return_value = {"sub": str(user_id), "type": "access"}
        user = make_mock_user(user_id=user_id)
        db = make_mock_db(user=user)

        result = await get_current_user(token="valid-token", db=db)
        assert result.id == user_id
        mock_decode.assert_called_once_with("valid-token")

    @pytest.mark.asyncio
    @patch("core.deps.decode_access_token")
    async def test_invalid_token_raises_401(self, mock_decode):
        mock_decode.return_value = None
        db = make_mock_db()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="bad-token", db=db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("core.deps.decode_access_token")
    async def test_missing_sub_raises_401(self, mock_decode):
        mock_decode.return_value = {"type": "access"}  # no "sub"
        db = make_mock_db()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="token", db=db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("core.deps.decode_access_token")
    async def test_invalid_uuid_sub_raises_401(self, mock_decode):
        mock_decode.return_value = {"sub": "not-a-uuid", "type": "access"}
        db = make_mock_db()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="token", db=db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("core.deps.decode_access_token")
    async def test_user_not_found_raises_401(self, mock_decode):
        user_id = uuid4()
        mock_decode.return_value = {"sub": str(user_id), "type": "access"}
        db = make_mock_db(user=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="token", db=db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("core.deps.decode_access_token")
    async def test_inactive_user_raises_403(self, mock_decode):
        user_id = uuid4()
        mock_decode.return_value = {"sub": str(user_id), "type": "access"}
        user = make_mock_user(user_id=user_id, is_active=False)
        db = make_mock_db(user=user)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="token", db=db)
        assert exc_info.value.status_code == 403
        assert "Inactive" in exc_info.value.detail


# =====================================================================
# require_admin
# =====================================================================

class TestRequireAdmin:

    @pytest.mark.asyncio
    async def test_admin_passes(self):
        admin = make_mock_user(role="ADMIN")
        result = await require_admin(current_user=admin)
        assert result.role == "ADMIN"

    @pytest.mark.asyncio
    async def test_non_admin_raises_403(self):
        user = make_mock_user(role="USER")
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=user)
        assert exc_info.value.status_code == 403
        assert "permissions" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_other_role_raises_403(self):
        user = make_mock_user(role="VIEWER")
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=user)
        assert exc_info.value.status_code == 403


        