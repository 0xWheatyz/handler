"""Password hashing and opaque-token helpers for user accounts.

Everything here is stdlib on purpose (``hashlib.scrypt`` + ``secrets``): no new
dependency for a code path every deployment runs. Passwords are stored as a
self-describing string carrying the scrypt parameters, so they can be raised later
without invalidating existing hashes. Session and reset tokens are random URL-safe
strings handed to the client; the database only ever stores their SHA-256, so a dump
never contains a usable credential.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# Interactive-login scrypt parameters (~16 MB memory, fast enough for a login form,
# expensive enough to make offline cracking of a leaked hash unattractive).
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32

MIN_PASSWORD_LENGTH = 8


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    """``scrypt$N$r$p$salt$key`` for storage in ``users.password_hash``."""
    salt = secrets.token_bytes(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=_KEY_BYTES,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time verification; False for malformed/absent hashes (an invited user
    who never set a password can't log in with anything)."""
    if not stored:
        return False
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(key)
        computed = hashlib.scrypt(
            password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(computed, expected)


def new_token() -> str:
    """An opaque bearer credential (session / reset / invite) for the client to hold."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """What the database stores in place of the token itself."""
    return hashlib.sha256(token.encode()).hexdigest()
