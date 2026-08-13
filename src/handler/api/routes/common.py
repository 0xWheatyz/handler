"""Small route helpers shared across project/agent-scoped endpoints.

Ownership rules (user accounts): every project is either **owned** by one user or
**shared** (owner NULL — legacy rows and anything an admin leaves communal). Admins and
legacy env tokens see everything; a regular user sees shared projects plus their own.
Mutations follow ``Actor.can_edit``: owners manage their projects, admins manage
everything, shared projects are admin-managed. Invisible resources 404 rather than 403,
so their existence is not leaked across the user boundary.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import Actor


def resolve_project(
    conn: Connection, project_id: str, actor: Actor, *, edit: bool = False
) -> dict:
    """Fetch a project the actor may see (404 otherwise); with ``edit=True`` also
    require mutation rights (403). This is the project-isolation choke point — every
    nested route resolves through here, so nothing crosses a project or user boundary."""
    project = repo.get_project(conn, project_id)
    if project is None or not actor.can_view(project.get("owner_user_id")):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"project '{project_id}' not found"
        )
    if edit and not actor.can_edit(project.get("owner_user_id")):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"project '{project_id}' is managed by its owner (or an admin)",
        )
    return project


def visible_project_ids(conn: Connection, actor: Actor) -> list[str] | None:
    """The project ids a non-admin user may see, or None for no restriction."""
    if actor.sees_all:
        return None
    return [p["id"] for p in repo.list_projects(conn, visible_to=actor.visible_scope)]


def resolve_agent(
    conn: Connection, project: str, name: str, actor: Actor, *, edit: bool = False
) -> dict:
    """Fetch an agent by ``(project, name)`` or 404, enforcing project visibility
    (README 3.4) — there is no path that returns another project's agent by accident."""
    resolve_project(conn, project, actor, edit=edit)
    agent = repo.get_agent_by_name(conn, project, name)
    if agent is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"agent '{name}' not found in project '{project}'",
        )
    return agent
