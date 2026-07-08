"""Small route helpers shared across agent-scoped endpoints."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import Connection

from ...db import repository as repo


def resolve_agent(conn: Connection, project: str, name: str) -> dict:
    """Fetch an agent by ``(project, name)`` or 404.

    Enforces project isolation (README 3.4): the lookup is always project-scoped, so
    there is no path that returns another project's agent by accident.
    """
    if repo.get_project(conn, project) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"project '{project}' not found")
    agent = repo.get_agent_by_name(conn, project, name)
    if agent is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"agent '{name}' not found in project '{project}'",
        )
    return agent
