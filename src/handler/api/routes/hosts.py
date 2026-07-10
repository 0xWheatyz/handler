"""Forge-host registry — the web-managed replacement for the hardcoded host->token-env map.

Registering a host lets ``control.credentials`` inject the right per-host token env var
(and scope the git credential helper) for self-hosted forges without a code change. The
registry only holds the env-var *name* and metadata — never a secret (secrets stay behind
``credential_ref`` pointers). Reads take the normal token; writes take the admin token.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import HostIn, HostOut, HostUpdateIn

router = APIRouter(prefix="/hosts", tags=["hosts"], dependencies=[Depends(require_auth)])


def _get_or_404(conn: Connection, hostname: str) -> dict:
    host = repo.get_host(conn, hostname)
    if host is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"host '{hostname}' not found")
    return host


@router.get("", response_model=list[HostOut])
def list_hosts(conn: Connection = Depends(db_conn)) -> list[dict]:
    return repo.list_hosts(conn)


@router.get("/{hostname}", response_model=HostOut)
def get_host(hostname: str, conn: Connection = Depends(db_conn)) -> dict:
    return _get_or_404(conn, hostname)


@router.post(
    "", response_model=HostOut, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_host(body: HostIn, conn: Connection = Depends(db_conn)) -> dict:
    if repo.get_host(conn, body.hostname) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"host '{body.hostname}' exists")
    try:
        return repo.create_host(
            conn,
            hostname=body.hostname,
            forge_type=body.forge_type,
            token_env_var=body.token_env_var,
            base_url=body.base_url,
        )
    except IntegrityError as exc:  # pragma: no cover - guarded above
        raise HTTPException(status.HTTP_409_CONFLICT, detail="host exists") from exc


@router.patch("/{hostname}", response_model=HostOut, dependencies=[Depends(require_admin)])
def update_host(
    hostname: str, body: HostUpdateIn, conn: Connection = Depends(db_conn)
) -> dict:
    _get_or_404(conn, hostname)
    return repo.update_host(conn, hostname, **body.model_dump(exclude_unset=True))


@router.delete("/{hostname}", dependencies=[Depends(require_admin)])
def delete_host(hostname: str, conn: Connection = Depends(db_conn)) -> dict:
    _get_or_404(conn, hostname)
    repo.delete_host(conn, hostname)
    return {"deleted": hostname}
