# backend/core/encryption.py
"""
Token encryption utilities using Fernet symmetric encryption.
"""
from cryptography.fernet import Fernet, InvalidToken
from core.config import settings

_SENTINEL_BYTES = {b"pending", b""}

def get_fernet() -> Fernet:
    if not settings.ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY not configured")
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
