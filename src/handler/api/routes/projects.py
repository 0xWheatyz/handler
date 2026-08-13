"""Project CRUD + project-scoped control actions.

Every route resolves through the ownership rules in ``routes.common``: users see shared
projects plus their own, admins (and legacy tokens) see everything, and mutations plus
the enqueue actions (sync, forge-init, poll-ci) require the owner or an admin. New
projects belong to the creating user (shared when registered with an env token).
"""

from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from ...config import get_settings
from ...db import repository as repo
from ..deps import Actor, db_conn, get_actor, require_auth
from ..schemas import CommandOut, ProjectCreatedOut, ProjectIn, ProjectOut, ProjectUpdateIn
from .common import resolve_project

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    actor: Actor = Depends(get_actor), conn: Connection = Depends(db_conn)
) -> list[dict]:
    return repo.list_projects(conn, visible_to=actor.visible_scope)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    return resolve_project(conn, project_id, actor)


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
def create_project(
    body: ProjectIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
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
            # The creating user owns their project; env tokens register shared ones.
            owner_user_id=actor.user_id,
        )
    except IntegrityError as exc:  # pragma: no cover - guarded above
        raise HTTPException(status.HTTP_409_CONFLICT, detail="project exists") from exc

    # Git-server mode always pulls: the worker clones (or fast-forwards) the repo into
    # root_dir. The command id lets the client watch the clone land.
    sync_command_id = None
    if git_remote:
        command = repo.enqueue_command(
            conn, "sync", project_id=project_id, requested_by=actor.label
        )
        sync_command_id = command["id"]

    # "Initialize mise": queue a bootstrap agent *after* the clone (FIFO by id, so the
    # sync runs first) to author a .mise.toml with a [tasks.test] task for the repo's
    # stack and commit + push it. It needs a remote to push, so skip when there is none.
    mise_init_command_id = None
    if body.init_mise and git_remote:
        mise_command = repo.enqueue_command(
            conn, "mise_init", project_id=project_id, requested_by=actor.label
        )
        mise_init_command_id = mise_command["id"]

    return {
        **project,
        "sync_command_id": sync_command_id,
        "mise_init_command_id": mise_init_command_id,
    }


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    body: ProjectUpdateIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    resolve_project(conn, project_id, actor, edit=True)
    fields = body.model_dump(exclude_unset=True)
    # Reassigning ownership (including back to shared) is an admin-only move.
    if "owner_user_id" in fields and not actor.is_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="only an admin can reassign a project's owner"
        )
    return repo.update_project(conn, project_id, **fields)


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    resolve_project(conn, project_id, actor, edit=True)
    repo.delete_project(conn, project_id)
    return {"deleted": project_id}


@router.post(
    "/{project_id}/forge-init",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_forge_init(
    project_id: str,
    no_commit: bool = False,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    resolve_project(conn, project_id, actor, edit=True)
    return repo.enqueue_command(
        conn,
        "forge_init",
        project_id=project_id,
        payload={"no_commit": no_commit},
        requested_by=actor.label,
    )


@router.post(
    "/{project_id}/sync",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_sync(
    project_id: str,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    """Clone-or-pull the project's repo now (the worker executes it)."""
    project = resolve_project(conn, project_id, actor, edit=True)
    if not project.get("git_remote"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"project '{project_id}' has no git_remote to sync from",
        )
    return repo.enqueue_command(
        conn, "sync", project_id=project_id, requested_by=actor.label
    )


@router.post(
    "/{project_id}/poll-ci",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_poll_ci(
    project_id: str,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    resolve_project(conn, project_id, actor, edit=True)
    return repo.enqueue_command(
        conn, "poll_ci", project_id=project_id, requested_by=actor.label
    )
