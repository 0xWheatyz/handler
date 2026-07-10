"""Shared dependencies: bearer auth and a per-request DB connection.

Auth is a single global token (README 3.3), compared in constant time. Shared-context
writes may require a separate higher-trust token (README 3.4), falling back to the
global token when unset.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Connection

from ..config import Settings, get_settings
from ..db.engine import connection

_bearer = HTTPBearer(auto_error=False)


def db_conn() -> Iterator[Connection]:
    with connection() as conn:
        yield conn


def _check(provided: str | None, expected: str) -> bool:
    if not expected or not provided:
        return False
    return secrets.compare_digest(provided, expected)


def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    token = creds.credentials if creds else None
    # The shared-context write and admin tokens are higher-trust, so they also grant
    # normal access; a single request carries one bearer, and it should never be rejected
    # for being the more privileged one.
    valid = (
        _check(token, settings.auth_token)
        or _check(token, settings.effective_shared_write_token)
        or _check(token, settings.effective_admin_token)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_shared_write(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    """Gate for shared_context writes — the one table every project implicitly trusts."""
    token = creds.credentials if creds else None
    if not _check(token, settings.effective_shared_write_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="shared-context write requires the shared-context write token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    """Gate for the web control surface: enqueuing control commands, project/host CRUD,
    and credential-pointer edits. Requires specifically the admin token (which defaults to
    the global token when ADMIN_TOKEN is unset)."""
    token = creds.credentials if creds else None
    if not _check(token, settings.effective_admin_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this action requires the admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )
