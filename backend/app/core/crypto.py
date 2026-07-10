"""Fernet-based encryption for stored connection secrets.

Note: Password hashing has been removed as the application uses OAuth/OIDC only.
This module derives a Fernet key from CREDENTIALS_ENCRYPTION_KEY/SALT to
encrypt and decrypt connection secrets (e.g. API-connect credentials) at rest.
"""

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from app.core.config import get_settings


def _derive_fernet_key() -> bytes:
    """Derive a Fernet key from the dedicated credential key + salt.

    Fails closed: raises if either secret is unset so a connection can never
    be stored or read without configured encryption.
    """
    settings = get_settings()
    key = settings.CREDENTIALS_ENCRYPTION_KEY
    salt = settings.CREDENTIALS_ENCRYPTION_SALT
    if not key or not salt:
        raise RuntimeError(
            "CREDENTIALS_ENCRYPTION_KEY and CREDENTIALS_ENCRYPTION_SALT must "
            "be set to store or read connection secrets"
        )
    kdf = Scrypt(salt=salt.encode(), length=32, n=2**14, r=8, p=1)
    return base64.urlsafe_b64encode(kdf.derive(key.encode()))


def encrypt_secret(plaintext: str) -> str:
    """Return a Fernet token for ``plaintext`` (URL-safe base64 string)."""
    return Fernet(_derive_fernet_key()).encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Return the plaintext for a Fernet ``token`` produced by encrypt."""
    return Fernet(_derive_fernet_key()).decrypt(token.encode()).decode()
