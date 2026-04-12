# backend/core/encryption.py
"""
Fernet symmetric encryption for OAuth access tokens stored at rest.

ENCRYPTION_KEY must be a URL-safe base64-encoded 32-byte key.
Generate with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Common mistake: secrets.token_hex(32) produces a 64-char hex string —
that is NOT a valid Fernet key and will raise ValueError here at startup.
"""

import base64
import binascii
import logging

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings

logger = logging.getLogger(__name__)

# Sentinel values stored in the DB before a real token is available.
# decrypt_token raises ValueError for these — callers should surface a reconnect prompt.
_SENTINEL_BYTES: set[bytes] = {b"pending", b"", b"revoked"}


def _validate_and_load() -> Fernet:
    """
    Validate ENCRYPTION_KEY at import time so misconfigurations surface
    during app startup — not on the first OAuth callback in production.

    Raises RuntimeError with an actionable fix message for every failure mode.
    """
    raw = settings.ENCRYPTION_KEY

    if not raw:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. "
            "Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    key_bytes = raw.strip().encode()

    # Detect the secrets.token_hex() mistake before Fernet gives a cryptic error.
    try:
        decoded = base64.urlsafe_b64decode(key_bytes + b"==")  # pad for urlsafe_b64decode
    except (binascii.Error, ValueError):
        raise RuntimeError(
            "ENCRYPTION_KEY is not valid base64url. "
            "Did you use secrets.token_hex()? That produces a hex string — not a Fernet key.\n"
            "Fix: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    if len(decoded) != 32:
        raise RuntimeError(
            f"ENCRYPTION_KEY decodes to {len(decoded)} bytes — Fernet requires exactly 32.\n"
            "Generate a fresh key:\n"
            "  python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    try:
        cipher = Fernet(key_bytes)
    except Exception as exc:
        raise RuntimeError(
            f"ENCRYPTION_KEY failed Fernet validation: {exc}\n"
            "Generate a fresh key:\n"
            "  python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        ) from exc

    logger.info("ENCRYPTION_KEY validated successfully (32-byte Fernet key).")
    return cipher


# Module-level singleton — one Fernet instance for the lifetime of the process.
# Validated once at startup; avoids re-instantiating on every encrypt/decrypt call.
_fernet: Fernet = _validate_and_load()


def encrypt_token(token: str) -> bytes:
    """
    Encrypt an OAuth access token for storage in the integrations table.
    Returns bytes matching the LargeBinary column type.
    """
    if not token:
        raise ValueError("Cannot encrypt an empty token.")
    return _fernet.encrypt(token.encode())


def decrypt_token(encrypted: bytes | str | None) -> str:
    """
    Decrypt a stored OAuth access token.

    Handles all forms the value may arrive in from the ORM:
      - None          → reconnect required
      - b"pending"    → reconnect required (token not yet stored)
      - b"revoked"    → reconnect required (token explicitly invalidated)
      - bytes/str     → decrypt and return plaintext

    Raises:
        ValueError: for None, empty, or sentinel values — caller should
            surface a reconnect CTA to the merchant.
        cryptography.fernet.InvalidToken: if ciphertext was encrypted under
            a different key (e.g. after ENCRYPTION_KEY rotation without
            re-encrypting stored tokens — see BUG-012).
    """
    if encrypted is None:
        raise ValueError("Token not set — reconnect required.")

    # Normalize: DB returns LargeBinary as bytes; guard against str callers.
    if isinstance(encrypted, str):
        encrypted = encrypted.encode()

    if encrypted in _SENTINEL_BYTES:
        raise ValueError("Token not set — reconnect required.")

    try:
        return _fernet.decrypt(encrypted).decode()
    except InvalidToken:
        logger.error(
            "decrypt_token: InvalidToken — ciphertext may have been encrypted under a "
            "different ENCRYPTION_KEY. This occurs after key rotation without re-encrypting "
            "stored tokens. See BUG-012 in BUGS.md."
        )
        raise ValueError("Token decryption failed — reconnect required.")


def rotate_token(old_ciphertext: bytes, new_key: str) -> bytes:
    """
    Re-encrypt a single token under a new Fernet key.

    Run this once per row in the integrations table during key rotation
    BEFORE updating ENCRYPTION_KEY in the environment.

    Usage:
        new_key = Fernet.generate_key().decode()
        for integration in session.query(Integration).all():
            if integration.access_token_encrypted not in (None, b"pending", b"revoked"):
                integration.access_token_encrypted = rotate_token(
                    integration.access_token_encrypted, new_key
                )
        session.commit()
        # Then update ENCRYPTION_KEY in Railway → redeploy.

    Args:
        old_ciphertext: Token encrypted under the current ENCRYPTION_KEY.
        new_key: New Fernet key string (base64url, decodes to 32 bytes).

    Returns:
        Token encrypted under new_key as bytes.
    """
    plaintext = decrypt_token(old_ciphertext)
    new_fernet = Fernet(new_key.encode())
    return new_fernet.encrypt(plaintext.encode())




    