# backend/core/encryption.py

"""
Token encryption utilities using Fernet symmetric encryption.
"""

from cryptography.fernet import Fernet

from core.config import settings


def get_fernet() -> Fernet:
    """Get Fernet instance with encryption key"""
    # Key should be 32 url-safe base64-encoded bytes
    # Generate with: Fernet.generate_key()
    key = settings.ENCRYPTION_KEY.encode()
    return Fernet(key)


def encrypt_token(token: str) -> bytes:
    """Encrypt a token string"""
    f = get_fernet()
    return f.encrypt(token.encode())


def decrypt_token(encrypted: bytes) -> str:
    """Decrypt a token"""
    f = get_fernet()
    return f.decrypt(encrypted).decode()
