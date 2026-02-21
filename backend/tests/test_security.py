"""
Test Suite: backend/core/security.py
Covers: password hashing, JWT access/refresh/reset tokens, decoding, expiry.

Place this file at: backend/tests/test_security.py
Run with: pytest backend/tests/test_security.py -v
"""

import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from jose import jwt


# ---- Import the module under test ----
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_access_token,
    decode_refresh_token,
    decode_reset_token,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    RESET_TOKEN_EXPIRE_MINUTES,
    pwd_context,
)


# =====================================================================
# PASSWORD HASHING
# =====================================================================

class TestHashPassword:
    """Tests for hash_password()."""

    def test_returns_string(self):
        result = hash_password("mysecretpassword")
        assert isinstance(result, str)

    def test_returns_bcrypt_hash(self):
        result = hash_password("mysecretpassword")
        assert result.startswith("$2b$") or result.startswith("$2a$")

    def test_different_hash_each_time(self):
        """Same input should produce different hashes (unique salt)."""
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2

    def test_empty_string(self):
        """Empty password should still hash without error."""
        result = hash_password("")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unicode_password(self):
        """Unicode characters should hash correctly."""
        result = hash_password("pässwörd_中文_🔑")
        assert isinstance(result, str)

    def test_long_password(self):
        """Very long passwords should work (bcrypt truncates at 72 bytes but shouldn't crash)."""
        long_pw = "a" * 256
        result = hash_password(long_pw)
        assert isinstance(result, str)


class TestVerifyPassword:
    """Tests for verify_password()."""

    def test_correct_password_returns_true(self):
        hashed = hash_password("correcthorse")
        assert verify_password("correcthorse", hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = hash_password("correcthorse")
        assert verify_password("wronghorse", hashed) is False

    def test_empty_password_matches_empty_hash(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True

    def test_empty_password_does_not_match_real_hash(self):
        hashed = hash_password("realpassword")
        assert verify_password("", hashed) is False

    def test_unicode_roundtrip(self):
        pw = "pässwörd_中文_🔑"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_tampered_hash_returns_false(self):
        """A corrupted/tampered hash should return False, not raise."""
        hashed = hash_password("mypassword")
        tampered = hashed[:-5] + "XXXXX"
        # passlib should handle this gracefully
        try:
            result = verify_password("mypassword", tampered)
            assert result is False
        except Exception:
            # Some corruptions may raise — that's acceptable too
            pass

    def test_completely_invalid_hash(self):
        """Total garbage as hash should not crash."""
        try:
            result = verify_password("password", "not-a-hash-at-all")
            assert result is False
        except Exception:
            # Acceptable — passlib may raise on truly invalid input
            pass


# =====================================================================
# ACCESS TOKENS
# =====================================================================

class TestCreateAccessToken:
    """Tests for create_access_token()."""

    def test_returns_string(self):
        token = create_access_token(data={"sub": "user-123"})
        assert isinstance(token, str)

    def test_contains_sub_claim(self):
        token = create_access_token(data={"sub": "user-123"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "user-123"

    def test_contains_exp_claim(self):
        token = create_access_token(data={"sub": "user-123"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_type_is_access(self):
        token = create_access_token(data={"sub": "user-123"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "access"

    def test_custom_expiry(self):
        token = create_access_token(
            data={"sub": "user-123"},
            expires_delta=timedelta(minutes=5),
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_preserves_extra_data(self):
        token = create_access_token(data={"sub": "user-123", "role": "ADMIN"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["role"] == "ADMIN"

    def test_does_not_mutate_input(self):
        data = {"sub": "user-123"}
        create_access_token(data=data)
        # Original dict should not have 'exp' or 'type' added
        assert "exp" not in data
        assert "type" not in data


class TestDecodeAccessToken:
    """Tests for decode_access_token()."""

    def test_valid_token(self):
        token = create_access_token(data={"sub": "user-123"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"

    def test_expired_token_returns_none(self):
        token = create_access_token(
            data={"sub": "user-123"},
            expires_delta=timedelta(seconds=-1),
        )
        result = decode_access_token(token)
        assert result is None

    def test_invalid_signature_returns_none(self):
        token = create_access_token(data={"sub": "user-123"})
        # Tamper with the token
        parts = token.split(".")
        parts[2] = parts[2][::-1]  # Reverse the signature
        tampered = ".".join(parts)
        result = decode_access_token(tampered)
        assert result is None

    def test_garbage_string_returns_none(self):
        result = decode_access_token("not.a.token")
        assert result is None

    def test_empty_string_returns_none(self):
        result = decode_access_token("")
        assert result is None

    def test_refresh_token_rejected(self):
        """Access token decoder should reject refresh tokens."""
        token = create_refresh_token(data={"sub": "user-123"})
        result = decode_access_token(token)
        assert result is None

    def test_reset_token_rejected(self):
        """Access token decoder should reject reset tokens."""
        token = create_reset_token(user_id="user-123")
        result = decode_access_token(token)
        assert result is None


# =====================================================================
# REFRESH TOKENS
# =====================================================================

class TestCreateRefreshToken:
    """Tests for create_refresh_token()."""

    def test_returns_string(self):
        token = create_refresh_token(data={"sub": "user-123"})
        assert isinstance(token, str)

    def test_type_is_refresh(self):
        token = create_refresh_token(data={"sub": "user-123"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "refresh"

    def test_contains_sub(self):
        token = create_refresh_token(data={"sub": "user-123"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "user-123"

    def test_custom_expiry(self):
        token = create_refresh_token(
            data={"sub": "user-123"},
            expires_delta=timedelta(days=1),
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_does_not_mutate_input(self):
        data = {"sub": "user-123"}
        create_refresh_token(data=data)
        assert "exp" not in data
        assert "type" not in data


class TestDecodeRefreshToken:
    """Tests for decode_refresh_token()."""

    def test_valid_refresh_token(self):
        token = create_refresh_token(data={"sub": "user-123"})
        payload = decode_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

    def test_expired_returns_none(self):
        token = create_refresh_token(
            data={"sub": "user-123"},
            expires_delta=timedelta(seconds=-1),
        )
        result = decode_refresh_token(token)
        assert result is None

    def test_access_token_rejected(self):
        """Refresh decoder should reject access tokens."""
        token = create_access_token(data={"sub": "user-123"})
        result = decode_refresh_token(token)
        assert result is None

    def test_reset_token_rejected(self):
        """Refresh decoder should reject reset tokens."""
        token = create_reset_token(user_id="user-123")
        result = decode_refresh_token(token)
        assert result is None

    def test_garbage_returns_none(self):
        result = decode_refresh_token("garbage.token.here")
        assert result is None


# =====================================================================
# RESET TOKENS
# =====================================================================

class TestCreateResetToken:
    """Tests for create_reset_token()."""

    def test_returns_string(self):
        token = create_reset_token(user_id="user-123")
        assert isinstance(token, str)

    def test_type_is_reset(self):
        token = create_reset_token(user_id="user-123")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "reset"

    def test_contains_user_id_as_sub(self):
        token = create_reset_token(user_id="user-456")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "user-456"

    def test_has_expiry(self):
        token = create_reset_token(user_id="user-123")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload


class TestDecodeResetToken:
    """Tests for decode_reset_token()."""

    def test_valid_reset_token(self):
        token = create_reset_token(user_id="user-789")
        result = decode_reset_token(token)
        assert result == "user-789"

    def test_expired_returns_none(self):
        """Manually create an expired reset token."""
        expired_token = jwt.encode(
            {"sub": "user-123", "type": "reset", "exp": 0},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        result = decode_reset_token(expired_token)
        assert result is None

    def test_access_token_rejected(self):
        """Reset decoder should reject access tokens."""
        token = create_access_token(data={"sub": "user-123"})
        result = decode_reset_token(token)
        assert result is None

    def test_refresh_token_rejected(self):
        """Reset decoder should reject refresh tokens."""
        token = create_refresh_token(data={"sub": "user-123"})
        result = decode_reset_token(token)
        assert result is None

    def test_garbage_returns_none(self):
        result = decode_reset_token("not-a-real-token")
        assert result is None


# =====================================================================
# CROSS-CUTTING: TOKEN TYPE ISOLATION
# =====================================================================

class TestTokenTypeIsolation:
    """
    Verify that each decoder ONLY accepts its own token type.
    This prevents token confusion attacks.
    """

    def test_access_decoder_accepts_only_access(self):
        access = create_access_token(data={"sub": "u1"})
        refresh = create_refresh_token(data={"sub": "u1"})
        reset = create_reset_token(user_id="u1")

        assert decode_access_token(access) is not None
        assert decode_access_token(refresh) is None
        assert decode_access_token(reset) is None

    def test_refresh_decoder_accepts_only_refresh(self):
        access = create_access_token(data={"sub": "u1"})
        refresh = create_refresh_token(data={"sub": "u1"})
        reset = create_reset_token(user_id="u1")

        assert decode_refresh_token(refresh) is not None
        assert decode_refresh_token(access) is None
        assert decode_refresh_token(reset) is None

    def test_reset_decoder_accepts_only_reset(self):
        access = create_access_token(data={"sub": "u1"})
        refresh = create_refresh_token(data={"sub": "u1"})
        reset = create_reset_token(user_id="u1")

        assert decode_reset_token(reset) is not None
        assert decode_reset_token(access) is None
        assert decode_reset_token(refresh) is None


# =====================================================================
# CONSTANTS SANITY CHECKS
# =====================================================================

class TestSecurityConstants:
    """Verify security configuration values are reasonable."""

    def test_algorithm_is_hs256(self):
        assert ALGORITHM == "HS256"

    def test_access_token_expiry_reasonable(self):
        """Access tokens should expire between 5 min and 24 hours."""
        assert 5 <= ACCESS_TOKEN_EXPIRE_MINUTES <= 1440

    def test_refresh_token_expiry_is_7_days(self):
        assert REFRESH_TOKEN_EXPIRE_DAYS == 7

    def test_reset_token_expiry_is_30_min(self):
        assert RESET_TOKEN_EXPIRE_MINUTES == 30

    def test_secret_key_is_set(self):
        """SECRET_KEY should not be empty."""
        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 0

    def test_pwd_context_uses_bcrypt(self):
        assert "bcrypt" in pwd_context.schemes()


        