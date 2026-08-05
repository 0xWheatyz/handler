"""Agent memory: the distilled note store and its link graph.

Agents write here through the bundled handler-memory MCP server (direct DB, like the
hooks); these routes are the dashboard's window plus the operator's editing surface —
no worker round-trip, nothing touches a live process, same trust model as the Claude
management pages. Reads take the normal token; writes take the admin token (the notes
feed every future agent's context, so authoring them is a control-surface action).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import (
    MemoryGraphOut,
    MemoryLinkIn,
    MemoryLinkOut,
    MemoryNoteIn,
    MemoryNoteOut,
    MemoryNoteUpdateIn,
)

router = APIRouter(prefix="/memory", tags=["memory"], dependencies=[Depends(require_auth)])


def _note_or_404(conn: Connection, note_id: int) -> dict:
    note = repo.get_memory_note(conn, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"note {note_id} not found")
    return note


def _project_or_400(conn: Connection, project_id: str | None) -> None:
    if project_id is not None and repo.get_project(conn, project_id) is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"project '{project_id}' not found"
        )


@router.get("/notes", response_model=list[MemoryNoteOut])
def list_notes(
    project_id: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    """Notes in scope, newest first; ``q`` switches to substring search (all terms)."""
    if q:
        return repo.search_memory_notes(conn, q, project_id=project_id, limit=limit)
    return repo.list_memory_notes(conn, project_id=project_id, limit=limit, offset=offset)


@router.get("/graph", response_model=MemoryGraphOut)
def graph(
    project_id: str | None = Query(None),
    conn: Connection = Depends(db_conn),
) -> dict:
    """The whole web of notes in one read — what the Memory page draws."""
    return repo.memory_graph(conn, project_id=project_id)


@router.get("/notes/{note_id}", response_model=MemoryNoteOut)
def get_note(note_id: int, conn: Connection = Depends(db_conn)) -> dict:
    return _note_or_404(conn, note_id)


@router.post(
    "/notes",
    response_model=MemoryNoteOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_note(body: MemoryNoteIn, conn: Connection = Depends(db_conn)) -> dict:
    _project_or_400(conn, body.project_id)
    return repo.create_memory_note(
        conn,
        title=body.title,
        body=body.body,
        kind=body.kind,
        project_id=body.project_id,
        agent_id=None,  # operator-authored; agents write via the MCP server
        tags=body.tags,
    )


@router.patch(
    "/notes/{note_id}", response_model=MemoryNoteOut, dependencies=[Depends(require_admin)]
)
def update_note(
    note_id: int, body: MemoryNoteUpdateIn, conn: Connection = Depends(db_conn)
) -> dict:
    _note_or_404(conn, note_id)
    fields = body.model_dump(exclude_unset=True)
    if "project_id" in fields:
        _project_or_400(conn, fields["project_id"])
    return repo.update_memory_note(conn, note_id, **fields)


@router.delete("/notes/{note_id}", dependencies=[Depends(require_admin)])
def delete_note(note_id: int, conn: Connection = Depends(db_conn)) -> dict:
    note = _note_or_404(conn, note_id)
    repo.delete_memory_note(conn, note_id)
    return {"deleted": note["id"]}


@router.post(
    "/links",
    response_model=MemoryLinkOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_link(body: MemoryLinkIn, conn: Connection = Depends(db_conn)) -> dict:
    if body.src_note_id == body.dst_note_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="a note cannot link to itself")
    _note_or_404(conn, body.src_note_id)
    _note_or_404(conn, body.dst_note_id)
    return repo.create_memory_link(
        conn, body.src_note_id, body.dst_note_id, relation=body.relation, agent_id=None
    )


@router.delete("/links/{link_id}", dependencies=[Depends(require_admin)])
def delete_link(link_id: int, conn: Connection = Depends(db_conn)) -> dict:
    if not repo.delete_memory_link(conn, link_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"link {link_id} not found")
    return {"deleted": link_id}
