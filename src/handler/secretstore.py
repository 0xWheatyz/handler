"""The encrypted secret store the ``db:`` credential scheme was reserved for.

Git-server tokens and SSH private keys are encrypted with a single symmetric key
(``HANDLER_SECRET_KEY``, a Fernet key) before they touch the database, and decrypted
only in the control layer at clone/spawn time. The database therefore still never
holds a *usable* secret: leaking a dump without the key leaks ciphertext.

The key lives only in the environment of the API (to encrypt on write) and the control
container (to decrypt on use) — set the same value on both.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


class SecretStoreError(Exception):
    """Raised when a secret cannot be encrypted or decrypted."""


def enabled() -> bool:
    """Whether a secret key is configured (storing secrets requires one)."""
    return bool(get_settings().handler_secret_key)


def _fernet() -> Fernet:
    key = get_settings().handler_secret_key
    if not key:
        raise SecretStoreError(
            "HANDLER_SECRET_KEY is not set: the encrypted secret store is disabled. "
            "Generate a key with python -c "
            '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" '
            "and set it on both the API and control containers."
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise SecretStoreError(
            "HANDLER_SECRET_KEY is not a valid Fernet key (32 urlsafe-base64 bytes)"
        ) from exc


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise SecretStoreError(
            "stored secret cannot be decrypted — was HANDLER_SECRET_KEY changed since "
            "it was saved?"
        ) from exc
