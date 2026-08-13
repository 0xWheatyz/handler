"""User accounts: sign-in, first-run setup, password resets, and admin user management.

The account model replaces "know the API key" for humans:

- **First run**: with zero accounts, ``POST /auth/setup`` creates the first one and it
  is the admin. The UI probes ``GET /auth/status`` (unauthenticated, boolean-only) to
  decide whether to show the setup form or the sign-in form.
- **Everyone after that** is created by an admin (``POST /auth/users``), which mints a
  one-shot **invite link**; the invitee sets their own password through it. With SMTP
  configured the link is emailed; either way it is returned to the admin.
- **Password reset**: self-serve ``POST /auth/forgot`` emails a short-lived reset link
  (silent about whether the address exists); an admin can also mint a link directly
  for any user. ``POST /auth/reset`` spends either kind of link.

Sessions are opaque bearer tokens (hash-stored, TTL from ``SESSION_TTL_DAYS``) used
exactly like the legacy env token — the client keeps calling with
``Authorization: Bearer …``. Legacy tokens stay valid for scripts/CI and break-glass.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import Connection

from ... import authn, emailer
from ...config import Settings, get_settings
from ...db import repository as repo
from ..deps import Actor, db_conn, get_actor, require_admin
from ..schemas import (
    AuthStatusOut,
    ChangePasswordIn,
    ForgotIn,
    ForgotOut,
    LoginIn,
    MeOut,
    ResetIn,
    ResetLinkOut,
    SessionOut,
    SetupIn,
    UserCreatedOut,
    UserCreateIn,
    UserOut,
    UserUpdateIn,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# A throwaway hash so a login attempt against an unknown email costs the same scrypt
# work as one against a real account (no timing oracle on address existence).
_DUMMY_HASH = authn.hash_password("not-a-real-password")


def _user_out(row: dict) -> dict:
    return {**row, "has_password": bool(row.get("password_hash"))}


def _new_session(conn: Connection, user: dict, settings: Settings) -> dict:
    repo.purge_expired_sessions(conn)  # piggybacked housekeeping — no scheduler needed
    token = authn.new_token()
    expires = datetime.now(UTC) + timedelta(days=settings.session_ttl_days)
    repo.create_auth_session(conn, user["id"], authn.hash_token(token), expires)
    return {"token": token, "user": _user_out(user)}


def _base_url(request: Request, settings: Settings) -> str:
    base = settings.public_base_url.strip() or str(request.base_url)
    return base.rstrip("/")


def _mint_link(
    conn: Connection, request: Request, settings: Settings, user: dict, purpose: str
) -> str:
    ttl_hours = (
        settings.invite_token_ttl_hours if purpose == "invite" else settings.reset_token_ttl_hours
    )
    token = authn.new_token()
    repo.create_auth_token(
        conn,
        user["id"],
        authn.hash_token(token),
        purpose,
        datetime.now(UTC) + timedelta(hours=ttl_hours),
    )
    return f"{_base_url(request, settings)}/reset?token={token}"


def _try_email(user: dict, subject: str, body: str, settings: Settings) -> bool:
    if not emailer.configured(settings):
        return False
    try:
        emailer.send(user["email"], subject, body, settings)
        return True
    except emailer.EmailError:
        # The link is still returned/usable; delivery failure must not lose it.
        return False


# ---- public (unauthenticated) ----------------------------------------------------------


@router.get("/status", response_model=AuthStatusOut)
def auth_status(conn: Connection = Depends(db_conn)) -> dict:
    return {
        "initialized": repo.count_users(conn) > 0,
        "smtp_configured": emailer.configured(get_settings()),
    }


@router.post("/setup", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def setup(body: SetupIn, conn: Connection = Depends(db_conn)) -> dict:
    """Create the first account — the admin. Refused once any account exists."""
    if repo.count_users(conn) > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="already set up — sign in, or ask an admin to invite you",
        )
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid email address")
    user = repo.create_user(
        conn, email, password_hash=authn.hash_password(body.password), is_admin=True
    )
    return _new_session(conn, user, get_settings())


@router.post("/login", response_model=SessionOut)
def login(body: LoginIn, conn: Connection = Depends(db_conn)) -> dict:
    user = repo.get_user_by_email(conn, body.email)
    stored = user["password_hash"] if user else _DUMMY_HASH
    if not authn.verify_password(body.password, stored) or user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
    if user["disabled"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="this account is disabled")
    return _new_session(conn, user, get_settings())


@router.post("/forgot", response_model=ForgotOut)
def forgot(
    body: ForgotIn, request: Request, conn: Connection = Depends(db_conn)
) -> dict:
    """Self-serve reset. Always answers ``ok`` — whether the address has an account is
    not revealed. Without SMTP nothing can be sent; the UI tells the user to ask an
    admin for a reset link instead."""
    settings = get_settings()
    if not emailer.configured(settings):
        return {"ok": True, "emailed": False}
    user = repo.get_user_by_email(conn, body.email)
    if user is not None and not user["disabled"] and user.get("password_hash"):
        link = _mint_link(conn, request, settings, user, "reset")
        _try_email(
            user,
            "Reset your Handler password",
            "A password reset was requested for this address.\n\n"
            f"Reset it here (link expires in {settings.reset_token_ttl_hours}h):\n{link}\n\n"
            "If you didn't request this, you can ignore this email.",
            settings,
        )
    return {"ok": True, "emailed": True}


@router.post("/reset", response_model=SessionOut)
def reset(body: ResetIn, conn: Connection = Depends(db_conn)) -> dict:
    """Spend a reset/invite link: set the password and sign the user in. Every other
    session for the account is revoked — a reset means the old credential is suspect."""
    token_row = repo.consume_auth_token(conn, authn.hash_token(body.token))
    if token_row is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="this link is invalid, expired, or already used — request a new one",
        )
    user = repo.get_user(conn, token_row["user_id"])
    if user is None or user["disabled"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="this account is disabled")
    user = repo.update_user(
        conn, user["id"], password_hash=authn.hash_password(body.password)
    )
    repo.delete_user_sessions(conn, user["id"])
    return _new_session(conn, user, get_settings())


# ---- authenticated self-service --------------------------------------------------------


@router.get("/me", response_model=MeOut)
def me(actor: Actor = Depends(get_actor)) -> dict:
    return {
        "kind": actor.kind,
        "user_id": actor.user_id,
        "email": actor.email,
        "is_admin": actor.is_admin,
    }


@router.post("/logout")
def logout(
    request: Request,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    """Revoke the presented session token. A no-op for legacy env tokens (they are
    configuration, not sessions)."""
    if actor.kind == "user":
        auth_header = request.headers.get("authorization", "")
        token = auth_header.split(" ", 1)[1] if " " in auth_header else ""
        repo.delete_auth_session(conn, authn.hash_token(token))
    return {"ok": True}


@router.post("/change-password")
def change_password(
    body: ChangePasswordIn,
    request: Request,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    if actor.kind != "user":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="env tokens have no password to change"
        )
    user = repo.get_user(conn, actor.user_id)
    if user is None or not authn.verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="current password is incorrect")
    repo.update_user(conn, user["id"], password_hash=authn.hash_password(body.new_password))
    # Sign out every *other* session; the one making this change keeps working.
    auth_header = request.headers.get("authorization", "")
    token = auth_header.split(" ", 1)[1] if " " in auth_header else ""
    repo.delete_user_sessions(conn, user["id"], keep_token_hash=authn.hash_token(token))
    return {"ok": True}


# ---- admin user management -------------------------------------------------------------


def _target_or_404(conn: Connection, user_id: int) -> dict:
    user = repo.get_user(conn, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"user {user_id} not found")
    return user


def _guard_last_admin(conn: Connection, target: dict, detail: str) -> None:
    """Refuse a change that would leave zero sign-in-capable admins (lockout guard).
    Only matters when the target currently counts as an active admin."""
    if (
        target["is_admin"]
        and not target["disabled"]
        and target.get("password_hash")
        and repo.count_active_admins(conn, exclude_user_id=target["id"]) == 0
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail)


@router.get("/users", response_model=list[UserOut], dependencies=[Depends(require_admin)])
def list_users(conn: Connection = Depends(db_conn)) -> list[dict]:
    return [_user_out(u) for u in repo.list_users(conn)]


@router.post(
    "/users",
    response_model=UserCreatedOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_user(
    body: UserCreateIn, request: Request, conn: Connection = Depends(db_conn)
) -> dict:
    settings = get_settings()
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid email address")
    if repo.get_user_by_email(conn, email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"'{email}' already has an account")
    user = repo.create_user(conn, email, password_hash=None, is_admin=body.is_admin)
    link = _mint_link(conn, request, settings, user, "invite")
    emailed = _try_email(
        user,
        "You've been invited to Handler",
        "An admin created a Handler account for this address.\n\n"
        f"Set your password here (link expires in {settings.invite_token_ttl_hours // 24} "
        f"days):\n{link}\n",
        settings,
    )
    return {"user": _user_out(user), "invite_url": link, "emailed": emailed}


@router.patch(
    "/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_admin)]
)
def update_user(
    user_id: int, body: UserUpdateIn, conn: Connection = Depends(db_conn)
) -> dict:
    target = _target_or_404(conn, user_id)
    fields = body.model_dump(exclude_unset=True)
    if fields.get("is_admin") is False or fields.get("disabled") is True:
        _guard_last_admin(
            conn, target, "refused: this is the last active admin — promote someone else first"
        )
    return _user_out(repo.update_user(conn, user_id, **fields))


@router.delete("/users/{user_id}", dependencies=[Depends(require_admin)])
def delete_user(
    user_id: int,
    actor: Actor = Depends(require_admin),
    conn: Connection = Depends(db_conn),
) -> dict:
    target = _target_or_404(conn, user_id)
    if actor.kind == "user" and actor.user_id == user_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="you can't delete your own account"
        )
    _guard_last_admin(
        conn, target, "refused: this is the last active admin — promote someone else first"
    )
    repo.delete_user(conn, user_id)
    return {"deleted": target["email"], "note": "their projects/skills/tools became shared"}


@router.post(
    "/users/{user_id}/reset-link",
    response_model=ResetLinkOut,
    dependencies=[Depends(require_admin)],
)
def mint_reset_link(
    user_id: int, request: Request, conn: Connection = Depends(db_conn)
) -> dict:
    """Admin-minted reset link — the escape hatch when SMTP is off (or the email never
    arrived). Uses invite semantics (longer TTL) for accounts that never set a password."""
    settings = get_settings()
    target = _target_or_404(conn, user_id)
    purpose = "invite" if not target.get("password_hash") else "reset"
    link = _mint_link(conn, request, settings, target, purpose)
    emailed = _try_email(
        target,
        "Reset your Handler password",
        f"An admin generated a password {purpose} link for your account:\n{link}\n",
        settings,
    )
    return {"reset_url": link, "emailed": emailed}
