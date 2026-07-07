"""The two explicit cross-project paths (README 3.4): the global log feed and the
shared-context key/value store. Reads use the normal token; writing a shared-context
key requires the higher-trust token.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import db_conn, require_auth, require_shared_write
from ..schemas import LogEntryOut, SharedContextIn, SharedContextOut

router = APIRouter(prefix="/shared", tags=["shared"], dependencies=[Depends(require_auth)])


@router.get("/log", response_model=list[LogEntryOut])
def shared_log(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    """Only entries explicitly marked ``global`` — a deliberate opt-in feed."""
    return repo.get_shared_log(conn, limit=limit, offset=offset)


@router.get("/context", response_model=list[SharedContextOut])
def shared_context(conn: Connection = Depends(db_conn)) -> list[dict]:
    return repo.get_shared_context(conn)


@router.get("/context/{key}", response_model=SharedContextOut)
def shared_context_key(key: str, conn: Connection = Depends(db_conn)) -> dict:
    row = repo.get_shared_context_key(conn, key)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"key '{key}' not set")
    return row


@router.put(
    "/context/{key}",
    response_model=SharedContextOut,
    dependencies=[Depends(require_shared_write)],
)
def put_shared_context(
    key: str,
    body: SharedContextIn,
    conn: Connection = Depends(db_conn),
) -> dict:
    return repo.set_shared_context(conn, key, body.value, agent_id=None)
