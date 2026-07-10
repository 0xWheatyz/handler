"""The command queue's read surface + the global poll-ci enqueue.

Every control action the dashboard triggers becomes a ``commands`` row; these routes let
the UI poll a command's status (queued -> running -> done/failed) and show an activity log.
Enqueuing project-scoped actions lives with those resources (agents/projects/approvals);
the one non-scoped action, a global CI sweep, is enqueued here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import CommandOut

router = APIRouter(tags=["commands"], dependencies=[Depends(require_auth)])


@router.get("/commands", response_model=list[CommandOut])
def list_commands(
    project: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return repo.list_commands(conn, project_id=project, limit=limit, offset=offset)


@router.get("/commands/{command_id}", response_model=CommandOut)
def get_command(command_id: int, conn: Connection = Depends(db_conn)) -> dict:
    command = repo.get_command(conn, command_id)
    if command is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"command {command_id} not found")
    return command


@router.post(
    "/poll-ci",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_global_poll_ci(conn: Connection = Depends(db_conn)) -> dict:
    """Enqueue a CI sweep across every project (per-project sweep is on the project route)."""
    return repo.enqueue_command(conn, "poll_ci", requested_by="operator:web")
