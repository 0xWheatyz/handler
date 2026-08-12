"""Shared dependencies: bearer auth (user sessions + legacy env tokens) and a
per-request DB connection.

Two kinds of callers hold a bearer token:

- **Users** — email + password accounts (``/auth``). Their bearer is an opaque session
  token minted at login; the database stores only its hash. A user is either an admin
  (sees and manages everything) or a regular account, which sees *shared* resources
  (owner NULL) plus its own — the per-user separation of projects, skills, and tools.
- **Legacy env tokens** — ``AUTH_TOKEN`` / ``SHARED_CONTEXT_WRITE_TOKEN`` /
  ``ADMIN_TOKEN``, compared in constant time exactly as before user accounts existed.
  They keep working for scripts/CI and as a break-glass credential, with their original
  semantics: they see every resource, and the admin token passes the admin gates.

Every request resolves to one :class:`Actor`; route handlers consult it for ownership
decisions (``visible_scope`` / ``can_edit``).
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Connection

from .. import authn
from ..config import Settings, get_settings
from ..db import repository as repo
from ..db.engine import connection

_bearer = HTTPBearer(auto_error=False)

# How stale a session's last_used_at may get before we write a fresh one (the dashboard
# polls every few seconds; a write per poll would be pure churn).
_TOUCH_INTERVAL = timedelta(minutes=5)


def db_conn() -> Iterator[Connection]:
    with connection() as conn:
        yield conn


def _check(provided: str | None, expected: str) -> bool:
    if not expected or not provided:
        return False
    return secrets.compare_digest(provided, expected)


@dataclass(frozen=True)
class Actor:
    """Who is making this request: a signed-in user or a legacy env token."""

    kind: str  # "user" | "token"
    user_id: int | None = None
    email: str | None = None
    is_admin: bool = False
    shared_write: bool = False  # may write shared_context keys

    @property
    def sees_all(self) -> bool:
        """Admins and legacy tokens see every resource (tokens keep their historical
        all-access semantics for scripts); regular users see shared + their own."""
        return self.is_admin or self.kind == "token"

    @property
    def visible_scope(self):
        """The ``visible_to`` argument for repository list functions."""
        return repo.VISIBLE_ALL if self.sees_all else self.user_id

    @property
    def label(self) -> str:
        """The ``requested_by`` audit label for commands this actor enqueues."""
        if self.kind == "user":
            return f"user:{self.user_id}:{self.email}"
        return "operator:web"

    def can_edit(self, owner_user_id: int | None) -> bool:
        """Mutation rule for owned resources: admins (and the legacy admin token) edit
        anything; a user edits what they own. Shared rows (owner NULL) are admin-managed."""
        if self.is_admin:
            return True
        if self.kind == "user":
            return owner_user_id is not None and owner_user_id == self.user_id
        return False

    def can_view(self, owner_user_id: int | None) -> bool:
        if self.sees_all:
            return True
        return owner_user_id is None or owner_user_id == self.user_id


def get_actor(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
    conn: Connection = Depends(db_conn),
) -> Actor:
    """Resolve the request's bearer to an :class:`Actor` or raise 401."""
    token = creds.credentials if creds else None
    if token is None:
        raise _unauthorized()

    # Legacy env tokens first (cheap constant-time compares). Order matters for the
    # historical fallbacks: with ADMIN_TOKEN unset it falls back to AUTH_TOKEN, so the
    # plain token must come out admin — checking the admin value first guarantees that.
    if _check(token, settings.effective_admin_token):
        return Actor(kind="token", is_admin=True, shared_write=True)
    if _check(token, settings.effective_shared_write_token):
        return Actor(kind="token", shared_write=True)
    if _check(token, settings.auth_token):
        return Actor(kind="token")

    # Otherwise it may be a user session token (hash-stored).
    token_hash = authn.hash_token(token)
    row = repo.get_session_user(conn, token_hash)
    if row is None:
        raise _unauthorized()
    last_used = row.get("session_last_used_at")
    if last_used is None or datetime.now(UTC) - last_used > _TOUCH_INTERVAL:
        repo.touch_auth_session(conn, token_hash)
    return Actor(
        kind="user",
        user_id=row["id"],
        email=row["email"],
        is_admin=bool(row["is_admin"]),
        shared_write=bool(row["is_admin"]),
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth(actor: Actor = Depends(get_actor)) -> Actor:
    return actor


def require_shared_write(actor: Actor = Depends(get_actor)) -> Actor:
    """Gate for shared_context writes — the one table every project implicitly trusts.
    Admin users, the admin token, and the dedicated shared-write token qualify."""
    if not actor.shared_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="shared-context write requires the shared-context write token or an admin",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return actor


def require_admin(actor: Actor = Depends(get_actor)) -> Actor:
    """Gate for the global control surface: git servers, the Claude account login,
    permission overrides, and user management. Admin users or the admin token."""
    if not actor.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this action requires an admin",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return actor
