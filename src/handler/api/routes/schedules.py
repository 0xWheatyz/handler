"""Recurring agent spawns (schedules).

A schedule fires an ordinary ``spawn`` command every ``interval_seconds`` — the worker
sweeps due rows on each loop pass and enqueues the spawn with a timestamped agent name,
so each run is a fresh, stateless agent. The canonical use: a standing prompt like
"Read @notes.md, continue from there, and overwrite that file before finishing", where
the file in the repo carries the state between runs.

Schedules belong to their project, so visibility and edit rights follow the project's
owner (a schedule ultimately runs ``claude`` against that project).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import Actor, db_conn, get_actor, require_auth
from ..schemas import ScheduleIn, ScheduleOut, ScheduleUpdateIn
from .common import resolve_project, visible_project_ids

router = APIRouter(tags=["schedules"], dependencies=[Depends(require_auth)])


def _schedule_or_404(conn: Connection, schedule_id: int) -> dict:
    schedule = repo.get_schedule(conn, schedule_id)
    if schedule is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"schedule {schedule_id} not found"
        )
    return schedule


def _check_model(conn: Connection, model_id: int | None, actor: Actor) -> None:
    """Fail-fast for the model dropdown, mirroring the spawn route: a stale or disabled
    selection bounces now instead of every firing failing asynchronously in Activity.
    Ownership counts too: another user's private backend is "not found" here."""
    if model_id is None:
        return
    model = repo.get_claude_model(conn, model_id)
    if model is None or not actor.can_view(model.get("owner_user_id")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"model {model_id} not found")
    if not model["enabled"]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"model backend '{model['name']}' is disabled"
        )


@router.get("/schedules", response_model=list[ScheduleOut])
def list_all_schedules(
    actor: Actor = Depends(get_actor), conn: Connection = Depends(db_conn)
) -> list[dict]:
    rows = repo.list_schedules(conn)
    visible = visible_project_ids(conn, actor)
    if visible is None:
        return rows
    allowed = set(visible)
    return [r for r in rows if r["project_id"] in allowed]


@router.get("/projects/{project_id}/schedules", response_model=list[ScheduleOut])
def list_project_schedules(
    project_id: str,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    resolve_project(conn, project_id, actor)
    return repo.list_schedules(conn, project_id)


@router.post(
    "/projects/{project_id}/schedules",
    response_model=ScheduleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    project_id: str,
    body: ScheduleIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    resolve_project(conn, project_id, actor, edit=True)
    _check_model(conn, body.model_id, actor)
    # next_run_at starts at now, so the first run fires on the worker's next pass — the
    # operator sees the schedule work immediately instead of waiting a full interval.
    return repo.create_schedule(
        conn,
        project_id=project_id,
        name_prefix=body.name_prefix.strip(),
        task=body.task,
        interval_seconds=body.interval_seconds,
        next_run_at=datetime.now(UTC),
        role=body.role,
        worktree=body.worktree,
        subdir=body.subdir,
        model_id=body.model_id,
        enabled=body.enabled,
    )


@router.patch(
    "/schedules/{schedule_id}",
    response_model=ScheduleOut,
)
def update_schedule(
    schedule_id: int,
    body: ScheduleUpdateIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    schedule = _schedule_or_404(conn, schedule_id)
    resolve_project(conn, schedule["project_id"], actor, edit=True)
    fields = body.model_dump(exclude_unset=True)
    if fields.get("model_id") is not None:
        _check_model(conn, fields["model_id"], actor)
    return repo.update_schedule(conn, schedule_id, **fields)


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    schedule = _schedule_or_404(conn, schedule_id)
    resolve_project(conn, schedule["project_id"], actor, edit=True)
    repo.delete_schedule(conn, schedule_id)
    return {"deleted": schedule_id}
