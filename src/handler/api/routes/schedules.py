"""Recurring agent spawns (schedules).

A schedule fires an ordinary ``spawn`` command every ``interval_seconds`` — the worker
sweeps due rows on each loop pass and enqueues the spawn with a timestamped agent name,
so each run is a fresh, stateless agent. The canonical use: a standing prompt like
"Read @notes.md, continue from there, and overwrite that file before finishing", where
the file in the repo carries the state between runs.

Reads take the normal token; writes take the admin token (a schedule ultimately runs
``claude`` in the control container).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import ScheduleIn, ScheduleOut, ScheduleUpdateIn

router = APIRouter(tags=["schedules"], dependencies=[Depends(require_auth)])


def _schedule_or_404(conn: Connection, schedule_id: int) -> dict:
    schedule = repo.get_schedule(conn, schedule_id)
    if schedule is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"schedule {schedule_id} not found"
        )
    return schedule


@router.get("/schedules", response_model=list[ScheduleOut])
def list_all_schedules(conn: Connection = Depends(db_conn)) -> list[dict]:
    return repo.list_schedules(conn)


@router.get("/projects/{project_id}/schedules", response_model=list[ScheduleOut])
def list_project_schedules(project_id: str, conn: Connection = Depends(db_conn)) -> list[dict]:
    return repo.list_schedules(conn, project_id)


@router.post(
    "/projects/{project_id}/schedules",
    response_model=ScheduleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_schedule(
    project_id: str, body: ScheduleIn, conn: Connection = Depends(db_conn)
) -> dict:
    if repo.get_project(conn, project_id) is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"project '{project_id}' not found"
        )
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
        enabled=body.enabled,
    )


@router.patch(
    "/schedules/{schedule_id}",
    response_model=ScheduleOut,
    dependencies=[Depends(require_admin)],
)
def update_schedule(
    schedule_id: int, body: ScheduleUpdateIn, conn: Connection = Depends(db_conn)
) -> dict:
    _schedule_or_404(conn, schedule_id)
    fields = body.model_dump(exclude_unset=True)
    return repo.update_schedule(conn, schedule_id, **fields)


@router.delete("/schedules/{schedule_id}", dependencies=[Depends(require_admin)])
def delete_schedule(schedule_id: int, conn: Connection = Depends(db_conn)) -> dict:
    _schedule_or_404(conn, schedule_id)
    repo.delete_schedule(conn, schedule_id)
    return {"deleted": schedule_id}
