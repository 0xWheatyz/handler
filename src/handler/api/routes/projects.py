"""Project CRUD + project-scoped control actions.

Reads and row registration take the normal token; edits/deletes and the enqueue actions
(forge-init, poll-ci) take the admin token. The agent *process* work (spawn/kill) lives in
``agents.py``; here we cover the project itself and the two project-wide control actions.
"""

from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from ...config import get_settings
from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import CommandOut, ProjectCreatedOut, ProjectIn, ProjectOut, ProjectUpdateIn

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


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-.")
    return slug or "project"


def _from_git_server(body: ProjectIn, conn: Connection) -> tuple[str, str, str]:
    """(id, root_dir, git_remote) for git-server mode.

    The remote prefers ssh when the server has a deploy key (that's what the key is
    for), else https (served by the stored token through the credential helper). The
    clone lands under ``PROJECTS_ROOT/<id>`` — stateless workflows don't care where.
    """
    host = repo.get_host(conn, body.git_server.strip().lower())
    if host is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=(
                f"git server '{body.git_server}' is not registered — "
                "add it under Git Servers first"
            ),
        )
    project_id = body.id or _slug(body.repo.split("/", 1)[1])
    if body.git_remote:
        remote = body.git_remote
    elif host.get("ssh_public_key"):
        remote = f"git@{host['hostname']}:{body.repo}.git"
    else:
        base = (host.get("base_url") or f"https://{host['hostname']}").rstrip("/")
        remote = f"{base}/{body.repo}.git"
    root_dir = os.path.join(get_settings().projects_root, project_id)
    return project_id, root_dir, remote


@router.post("", response_model=ProjectCreatedOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectIn, conn: Connection = Depends(db_conn)) -> dict:
    if body.git_server:
        project_id, root_dir, git_remote = _from_git_server(body, conn)
    else:
        project_id, root_dir, git_remote = body.id, body.root_dir, body.git_remote

    if repo.get_project(conn, project_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"project '{project_id}' exists")
    try:
        project = repo.create_project(
            conn,
            project_id=project_id,
            root_dir=root_dir,
            git_remote=git_remote,
            credential_ref=body.credential_ref,
        )
    except IntegrityError as exc:  # pragma: no cover - guarded above
        raise HTTPException(status.HTTP_409_CONFLICT, detail="project exists") from exc

    # Git-server mode always pulls: the worker clones (or fast-forwards) the repo into
    # root_dir. The command id lets the client watch the clone land.
    sync_command_id = None
    if git_remote:
        command = repo.enqueue_command(
            conn, "sync", project_id=project_id, requested_by="operator:web"
        )
        sync_command_id = command["id"]

    # "Initialize mise": queue a bootstrap agent *after* the clone (FIFO by id, so the
    # sync runs first) to author a .mise.toml with a [tasks.test] task for the repo's
    # stack and commit + push it. It needs a remote to push, so skip when there is none.
    mise_init_command_id = None
    if body.init_mise and git_remote:
        mise_command = repo.enqueue_command(
            conn, "mise_init", project_id=project_id, requested_by="operator:web"
        )
        mise_init_command_id = mise_command["id"]

    return {
        **project,
        "sync_command_id": sync_command_id,
        "mise_init_command_id": mise_init_command_id,
    }


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
    "/{project_id}/sync",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_sync(project_id: str, conn: Connection = Depends(db_conn)) -> dict:
    """Clone-or-pull the project's repo now (the worker executes it)."""
    project = _get_or_404(conn, project_id)
    if not project.get("git_remote"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"project '{project_id}' has no git_remote to sync from",
        )
    return repo.enqueue_command(
        conn, "sync", project_id=project_id, requested_by="operator:web"
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
