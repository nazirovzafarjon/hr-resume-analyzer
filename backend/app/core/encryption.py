"""Authenticated encryption for secrets stored in PostgreSQL.

Used for the AI provider API keys HR users save in Settings. Fernet
(AES-128-CBC + HMAC-SHA256, from the ``cryptography`` package) detects any
tampering on decrypt. The key comes only from ``AI_CREDENTIAL_ENCRYPTION_KEY``
in the environment; it is never stored in the database or returned by the API.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionUnavailableError(Exception):
    """No (valid) encryption key is configured on the server."""


class DecryptionError(Exception):
    """A stored value could not be decrypted (wrong key or tampered data)."""


def _fernet() -> Fernet:
    key = settings.AI_CREDENTIAL_ENCRYPTION_KEY.strip()
    if not key:
        raise EncryptionUnavailableError("AI_CREDENTIAL_ENCRYPTION_KEY is not set")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise EncryptionUnavailableError(
            "AI_CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key"
        ) from exc


def encryption_available() -> bool:
    """True when secrets can be encrypted with the configured key."""
    try:
        _fernet()
    except EncryptionUnavailableError:
        return False
    return True


def encrypt_secret(plaintext: str) -> str:
    """Encrypt ``plaintext`` and return the token as text."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Decrypt a value produced by :func:`encrypt_secret`."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("stored secret could not be decrypted") from exc
