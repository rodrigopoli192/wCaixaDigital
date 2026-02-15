"""
Custom encrypted model fields using Fernet symmetric encryption.

Uses the `cryptography` library (already a project dependency) to transparently
encrypt/decrypt values at the database layer. The encryption key is derived
from Django's SECRET_KEY via PBKDF2, so no extra environment variable is needed.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet() -> Fernet:
    """Derive a Fernet key from SECRET_KEY using PBKDF2."""
    key_material = hashlib.pbkdf2_hmac(
        "sha256",
        settings.SECRET_KEY.encode(),
        b"encrypted-field-salt",
        iterations=100_000,
    )
    fernet_key = base64.urlsafe_b64encode(key_material[:32])
    return Fernet(fernet_key)


def _is_encrypted(value: str) -> bool:
    """Check if a value looks like a Fernet token (starts with 'gAAAAA')."""
    return isinstance(value, str) and value.startswith("gAAAAA")


class EncryptedCharField(models.CharField):
    """CharField that transparently encrypts/decrypts via Fernet."""

    def get_prep_value(self, value):
        """Encrypt before saving to the database."""
        if value is None or value == "":
            return value
        if _is_encrypted(value):
            return value
        fernet = _get_fernet()
        return fernet.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        """Decrypt when reading from the database."""
        if value is None or value == "":
            return value
        if not _is_encrypted(value):
            return value
        try:
            fernet = _get_fernet()
            return fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            return value
