# backend/core/encryption.py
"""
Token encryption utilities using Fernet symmetric encryption.
"""
import logging

from cryptography.fernet import Fernet, InvalidToken
from core.config import settings

logger = logging.getLogger(__name__)

_SENTINEL_BYTES = {b"pending", b""}


def _validate_encryption_key() -> None:
    """Validate ENCRYPTION_KEY at startup so misconfigurations fail fast."""
    if not settings.ENCRYPTION_KEY:
        raise RuntimeError(
            "ENCRYPTION_KEY not configured. Set a valid Fernet key in environment variables."
        )
    try:
        Fernet(settings.ENCRYPTION_KEY.encode())
    except (ValueError, Exception) as e:
        raise RuntimeError(
            f"ENCRYPTION_KEY is malformed (not a valid Fernet key): {e}"
        ) from e
    logger.info("ENCRYPTION_KEY validated successfully")


# Fail fast at import time — surfaces during app startup, not on first OAuth call
_validate_encryption_key()


def get_fernet() -> Fernet:
    return Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_token(token: str) -> bytes:
    return get_fernet().encrypt(token.encode())

def decrypt_token(encrypted: bytes | str | None) -> str:
    if encrypted is None:
        raise ValueError("Token not set — reconnect required")
    # Normalize to bytes: DB stores access_token_encrypted as LargeBinary (bytes);
    # guard against callers passing a decoded string.
    if isinstance(encrypted, str):
        encrypted = encrypted.encode()
    if encrypted in _SENTINEL_BYTES:
        raise ValueError("Token not set — reconnect required")
    try:
        return get_fernet().decrypt(encrypted).decode()
    except InvalidToken:
        raise ValueError("Token decryption failed — reconnect required")
