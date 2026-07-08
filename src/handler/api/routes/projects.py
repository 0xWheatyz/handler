"""Project registration + listing (control-plane; the process spawn is the CLI's job)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from ...db import repository as repo
from ..deps import db_conn, require_auth
from ..schemas import ProjectIn, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[ProjectOut])
def list_projects(conn: Connection = Depends(db_conn)) -> list[dict]:
    return repo.list_projects(conn)


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
