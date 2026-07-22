"""Agent listing/registration, read views (checkmark, log), and lifecycle actions.

The agent *row* is registered here; the agent *process* (tmux + claude) is created by the
control worker, so ``spawn``/``kill`` enqueue a command (admin-gated) rather than acting
in-process — the API container has no tmux/git/claude and does not own the sessions. All
routes are nested under ``/projects/{project}`` so nothing crosses a project boundary.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import (
    AgentEventOut,
    AgentIn,
    AgentOut,
    CheckmarkOut,
    CommandOut,
    LogEntryOut,
    SpawnIn,
)
from .common import resolve_agent

router = APIRouter(
    prefix="/projects/{project}/agents",
    tags=["agents"],
    dependencies=[Depends(require_auth)],
)


def _require_project(conn: Connection, project: str) -> None:
    if repo.get_project(conn, project) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"project '{project}' not found")


@router.get("", response_model=list[AgentOut])
def list_agents(project: str, conn: Connection = Depends(db_conn)) -> list[dict]:
    _require_project(conn, project)
    return repo.list_agents(conn, project)


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(project: str, body: AgentIn, conn: Connection = Depends(db_conn)) -> dict:
    _require_project(conn, project)
    if repo.get_agent_by_name(conn, project, body.name) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"agent '{body.name}' exists in project '{project}'",
        )
    try:
        return repo.create_agent(
            conn,
            project_id=project,
            name=body.name,
            working_dir=body.working_dir,
            status=body.status,
            role=body.role,
        )
    except IntegrityError as exc:  # pragma: no cover - guarded above
        raise HTTPException(status.HTTP_409_CONFLICT, detail="agent exists") from exc


@router.post(
    "/spawn",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_spawn(project: str, body: SpawnIn, conn: Connection = Depends(db_conn)) -> dict:
    """Enqueue a spawn; the worker creates the agent row + claude process and reports back."""
    _require_project(conn, project)
    if repo.get_agent_by_name(conn, project, body.name) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"agent '{body.name}' already exists in project '{project}'",
        )
    if not body.task:
        # A headless `claude -p` run with no prompt exits immediately having done
        # nothing. Reject here (400) instead of letting the command fail asynchronously
        # in the worker.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="a task is required: the headless runner has no idle-REPL mode",
        )
    payload = body.model_dump(exclude={"name"}, exclude_none=True)
    return repo.enqueue_command(
        conn,
        "spawn",
        project_id=project,
        agent_name=body.name,
        payload=payload,
        requested_by="operator:web",
    )


@router.post(
    "/{name}/kill",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_kill(project: str, name: str, conn: Connection = Depends(db_conn)) -> dict:
    resolve_agent(conn, project, name)
    return repo.enqueue_command(
        conn, "kill", project_id=project, agent_name=name, requested_by="operator:web"
    )


@router.delete("/{name}", dependencies=[Depends(require_admin)])
def delete_agent(project: str, name: str, conn: Connection = Depends(db_conn)) -> dict:
    """Remove the agent row (does not kill a live session — kill first)."""
    resolve_agent(conn, project, name)
    repo.delete_agent(conn, project, name)
    return {"deleted": name}


@router.get("/{name}/checkmark", response_model=CheckmarkOut)
def get_checkmark(project: str, name: str, conn: Connection = Depends(db_conn)) -> dict:
    agent = resolve_agent(conn, project, name)
    checkmark = repo.get_checkmark(conn, agent["id"])
    if checkmark is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"agent '{name}' has no checkmark yet",
        )
    return checkmark


@router.get("/{name}/events", response_model=list[AgentEventOut])
def get_events(
    project: str,
    name: str,
    after_id: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    """The headless run event stream, oldest-first, cursor-paged by row id.

    The UI polls with ``after_id`` = the largest id it has seen, so each poll returns
    only new events (an empty list for a legacy tmux agent or an idle one).
    """
    agent = resolve_agent(conn, project, name)
    return repo.list_agent_events(conn, agent["id"], after_id=after_id, limit=limit)


@router.get("/{name}/log", response_model=list[LogEntryOut])
def get_log(
    project: str,
    name: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    agent = resolve_agent(conn, project, name)
    return repo.get_log(conn, agent["id"], limit=limit, offset=offset)
