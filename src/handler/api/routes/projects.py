"""Project CRUD + project-scoped control actions.

Reads and row registration take the normal token; edits/deletes and the enqueue actions
(forge-init, poll-ci) take the admin token. The agent *process* work (spawn/kill) lives in
``agents.py``; here we cover the project itself and the two project-wide control actions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import CommandOut, ProjectIn, ProjectOut, ProjectUpdateIn

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_auth)])


def _get_or_404(conn: Connection, project_id: str) -> dict:
    project = repo.get_project(conn, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"project '{project_id}' not found")
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(conn: Connection = Depends(db_conn)) -> list[dict]:
    return repo.list_projects(conn)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, conn: Connection = Depends(db_conn)) -> dict:
    return _get_or_404(conn, project_id)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectIn, conn: Connection = Depends(db_conn)) -> dict:
    if repo.get_project(conn, body.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"project '{body.id}' exists")
    try:
        return repo.create_project(
            conn,
            project_id=body.id,
            root_dir=body.root_dir,
            git_remote=body.git_remote,
            credential_ref=body.credential_ref,
        )
    except IntegrityError as exc:  # pragma: no cover - guarded above
        raise HTTPException(status.HTTP_409_CONFLICT, detail="project exists") from exc


@router.patch("/{project_id}", response_model=ProjectOut, dependencies=[Depends(require_admin)])
def update_project(
    project_id: str, body: ProjectUpdateIn, conn: Connection = Depends(db_conn)
) -> dict:
    _get_or_404(conn, project_id)
    fields = body.model_dump(exclude_unset=True)
    return repo.update_project(conn, project_id, **fields)


@router.delete("/{project_id}", dependencies=[Depends(require_admin)])
def delete_project(project_id: str, conn: Connection = Depends(db_conn)) -> dict:
    _get_or_404(conn, project_id)
    repo.delete_project(conn, project_id)
    return {"deleted": project_id}


@router.post(
    "/{project_id}/forge-init",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_forge_init(
    project_id: str, no_commit: bool = False, conn: Connection = Depends(db_conn)
) -> dict:
    _get_or_404(conn, project_id)
    return repo.enqueue_command(
        conn,
        "forge_init",
        project_id=project_id,
        payload={"no_commit": no_commit},
        requested_by="operator:web",
    )


@router.post(
    "/{project_id}/poll-ci",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_poll_ci(project_id: str, conn: Connection = Depends(db_conn)) -> dict:
    _get_or_404(conn, project_id)
    return repo.enqueue_command(
        conn, "poll_ci", project_id=project_id, requested_by="operator:web"
    )
