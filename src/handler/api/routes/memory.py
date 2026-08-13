"""Agent memory: the distilled note store and its link graph.

Agents write here through the bundled handler-memory MCP server (direct DB, like the
hooks); these routes are the dashboard's window plus the operator's editing surface —
no worker round-trip, nothing touches a live process, same trust model as the Claude
management pages. Visibility follows the note's project (global notes are visible to
everyone); writing follows edit rights — a project's owner (or an admin) authors its
notes, and **global** notes are admin-only, since they feed every future agent's
context across every user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import Actor, db_conn, get_actor, require_auth
from ..schemas import (
    MemoryGraphOut,
    MemoryLinkIn,
    MemoryLinkOut,
    MemoryNoteIn,
    MemoryNoteOut,
    MemoryNoteUpdateIn,
)
from .common import resolve_project, visible_project_ids

router = APIRouter(prefix="/memory", tags=["memory"], dependencies=[Depends(require_auth)])


def _note_or_404(conn: Connection, note_id: int, actor: Actor) -> dict:
    note = repo.get_memory_note(conn, note_id)
    if note is not None and note.get("project_id") is not None and not actor.sees_all:
        project = repo.get_project(conn, note["project_id"])
        if project is None or not actor.can_view(project.get("owner_user_id")):
            note = None
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"note {note_id} not found")
    return note


def _require_note_edit(conn: Connection, note_project_id: str | None, actor: Actor) -> None:
    """Edit gate for a note's scope: project notes follow the project's owner; global
    notes are admin-only (they reach every user's agents)."""
    if note_project_id is None:
        if not actor.is_admin:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail="global notes are admin-managed"
            )
        return
    project = repo.get_project(conn, note_project_id)
    if project is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"project '{note_project_id}' not found"
        )
    resolve_project(conn, note_project_id, actor, edit=True)


@router.get("/notes", response_model=list[MemoryNoteOut])
def list_notes(
    project_id: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    """Notes in scope, newest first; ``q`` switches to substring search (all terms)."""
    visible = visible_project_ids(conn, actor)
    if q:
        return repo.search_memory_notes(
            conn, q, project_id=project_id, limit=limit, visible_project_ids=visible
        )
    return repo.list_memory_notes(
        conn, project_id=project_id, limit=limit, offset=offset, visible_project_ids=visible
    )


@router.get("/graph", response_model=MemoryGraphOut)
def graph(
    project_id: str | None = Query(None),
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    """The whole web of notes in one read — what the Memory page draws."""
    return repo.memory_graph(
        conn, project_id=project_id, visible_project_ids=visible_project_ids(conn, actor)
    )


@router.get("/notes/{note_id}", response_model=MemoryNoteOut)
def get_note(
    note_id: int,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    return _note_or_404(conn, note_id, actor)


@router.post(
    "/notes",
    response_model=MemoryNoteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    body: MemoryNoteIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    _require_note_edit(conn, body.project_id, actor)
    return repo.create_memory_note(
        conn,
        title=body.title,
        body=body.body,
        kind=body.kind,
        project_id=body.project_id,
        agent_id=None,  # operator-authored; agents write via the MCP server
        tags=body.tags,
    )


@router.patch("/notes/{note_id}", response_model=MemoryNoteOut)
def update_note(
    note_id: int,
    body: MemoryNoteUpdateIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    note = _note_or_404(conn, note_id, actor)
    _require_note_edit(conn, note.get("project_id"), actor)
    fields = body.model_dump(exclude_unset=True)
    if "project_id" in fields and fields["project_id"] != note.get("project_id"):
        # Moving a note is an edit of both scopes (the old one loses it, the new gains it).
        _require_note_edit(conn, fields["project_id"], actor)
    return repo.update_memory_note(conn, note_id, **fields)


@router.delete("/notes/{note_id}")
def delete_note(
    note_id: int,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    note = _note_or_404(conn, note_id, actor)
    _require_note_edit(conn, note.get("project_id"), actor)
    repo.delete_memory_note(conn, note_id)
    return {"deleted": note["id"]}


@router.post(
    "/links",
    response_model=MemoryLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def create_link(
    body: MemoryLinkIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    if body.src_note_id == body.dst_note_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="a note cannot link to itself")
    src = _note_or_404(conn, body.src_note_id, actor)
    dst = _note_or_404(conn, body.dst_note_id, actor)
    _require_note_edit(conn, src.get("project_id"), actor)
    _require_note_edit(conn, dst.get("project_id"), actor)
    return repo.create_memory_link(
        conn, body.src_note_id, body.dst_note_id, relation=body.relation, agent_id=None
    )


@router.delete("/links/{link_id}")
def delete_link(
    link_id: int,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    link = repo.get_memory_link(conn, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"link {link_id} not found")
    src = _note_or_404(conn, link["src_note_id"], actor)
    dst = _note_or_404(conn, link["dst_note_id"], actor)
    _require_note_edit(conn, src.get("project_id"), actor)
    _require_note_edit(conn, dst.get("project_id"), actor)
    repo.delete_memory_link(conn, link_id)
    return {"deleted": link_id}
