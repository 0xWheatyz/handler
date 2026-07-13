"""Claude Code web-login: enqueue the two-step ``/login`` flow the worker runs.

The API container has no ``claude`` binary and doesn't own the tmux sessions, so — like
spawn/kill — logging Claude Code in is a control command the worker executes in the
control container:

- ``POST /login/start``  enqueues ``login_start``; its result carries the ``url`` the UI
  opens (in an iframe) for the operator to authorize.
- ``POST /login/submit`` enqueues ``login_submit`` with the pasted ``code``; its result
  carries ``success``.

Both are admin-gated (they act on the host's Claude credentials). The UI polls
``GET /commands/{id}`` for each, exactly as it does for spawns.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import CommandOut, LoginSubmitIn

router = APIRouter(tags=["login"], dependencies=[Depends(require_auth)])


@router.post(
    "/login/start",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_login_start(conn: Connection = Depends(db_conn)) -> dict:
    """Open ``claude /login`` in the control container and return the authorization URL."""
    return repo.enqueue_command(conn, "login_start", requested_by="operator:web")


@router.post(
    "/login/submit",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_login_submit(body: LoginSubmitIn, conn: Connection = Depends(db_conn)) -> dict:
    """Feed the pasted authorization code back into the waiting login session."""
    return repo.enqueue_command(
        conn,
        "login_submit",
        payload={"code": body.code},
        requested_by="operator:web",
    )
