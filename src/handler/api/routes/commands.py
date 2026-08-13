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
from ..deps import Actor, db_conn, get_actor, require_admin, require_auth
from ..schemas import CommandOut
from .common import visible_project_ids

router = APIRouter(tags=["commands"], dependencies=[Depends(require_auth)])


@router.get("/commands", response_model=list[CommandOut])
def list_commands(
    project: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    """The activity feed. Non-admin users see commands on projects they can see, plus
    non-project commands they enqueued themselves (so they can track e.g. an install)."""
    return repo.list_commands(
        conn,
        project_id=project,
        limit=limit,
        offset=offset,
        restrict_to_projects=visible_project_ids(conn, actor),
        or_requested_by=actor.label,
    )


@router.get("/commands/{command_id}", response_model=CommandOut)
def get_command(
    command_id: int,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    command = repo.get_command(conn, command_id)
    if command is not None and not actor.sees_all:
        visible = set(visible_project_ids(conn, actor) or [])
        if command.get("project_id") not in visible and command.get("requested_by") != actor.label:
            command = None
    if command is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"command {command_id} not found")
    return command


@router.post(
    "/poll-ci",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_global_poll_ci(
    actor: Actor = Depends(require_admin), conn: Connection = Depends(db_conn)
) -> dict:
    """Enqueue a CI sweep across every project (per-project sweep is on the project route)."""
    return repo.enqueue_command(conn, "poll_ci", requested_by=actor.label)
