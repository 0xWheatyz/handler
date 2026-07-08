"""Agent listing/registration and the read views (checkmark, log).

The agent *row* is registered here (the API mirror listed in README 3.3); the agent
*process* is spawned by the control CLI. All routes are nested under
``/projects/{project}`` so nothing crosses a project boundary.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from ...db import repository as repo
from ..deps import db_conn, require_auth
from ..schemas import AgentIn, AgentOut, CheckmarkOut, LogEntryOut
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
        )
    except IntegrityError as exc:  # pragma: no cover - guarded above
        raise HTTPException(status.HTTP_409_CONFLICT, detail="agent exists") from exc


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
