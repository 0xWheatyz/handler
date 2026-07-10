"""Git-server registry — hosts, their token env mapping, and their own credentials.

Each row maps a host to the token env var to inject at spawn, and may carry the
server's credentials itself: a forge token (encrypted with ``HANDLER_SECRET_KEY``
before it reaches the database) and an ed25519 deploy keypair whose public half is
returned so the operator can paste it into the forge. The API never returns the token
or the private key — responses expose only ``has_token`` and ``ssh_public_key``.
Reads take the normal token; writes take the admin token.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from ... import secretstore, sshkeys
from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import HostIn, HostOut, HostUpdateIn

router = APIRouter(prefix="/hosts", tags=["hosts"], dependencies=[Depends(require_auth)])


def _get_or_404(conn: Connection, hostname: str) -> dict:
    host = repo.get_host(conn, hostname)
    if host is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"host '{hostname}' not found")
    return host


def _public(row: dict) -> dict:
    """A host row shaped for responses: secrets replaced by the ``has_token`` flag."""
    return {**row, "has_token": bool(row.get("token_enc"))}


def _encrypt_or_400(value: str, what: str) -> str:
    try:
        return secretstore.encrypt(value)
    except secretstore.SecretStoreError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"cannot store {what}: {exc}"
        ) from exc


@router.get("", response_model=list[HostOut])
def list_hosts(conn: Connection = Depends(db_conn)) -> list[dict]:
    return [_public(h) for h in repo.list_hosts(conn)]


@router.get("/{hostname}", response_model=HostOut)
def get_host(hostname: str, conn: Connection = Depends(db_conn)) -> dict:
    return _public(_get_or_404(conn, hostname))


@router.post(
    "", response_model=HostOut, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_host(body: HostIn, conn: Connection = Depends(db_conn)) -> dict:
    if repo.get_host(conn, body.hostname) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"host '{body.hostname}' exists")

    token_enc = _encrypt_or_400(body.token, "the forge token") if body.token else None
    ssh_public_key = ssh_private_key_enc = None
    if body.generate_ssh_key:
        private_key, ssh_public_key = sshkeys.generate_keypair(f"handler@{body.hostname}")
        ssh_private_key_enc = _encrypt_or_400(private_key, "the SSH private key")

    try:
        return _public(
            repo.create_host(
                conn,
                hostname=body.hostname,
                forge_type=body.forge_type,
                token_env_var=body.token_env_var,
                base_url=body.base_url,
                token_enc=token_enc,
                ssh_public_key=ssh_public_key,
                ssh_private_key_enc=ssh_private_key_enc,
            )
        )
    except IntegrityError as exc:  # pragma: no cover - guarded above
        raise HTTPException(status.HTTP_409_CONFLICT, detail="host exists") from exc


@router.patch("/{hostname}", response_model=HostOut, dependencies=[Depends(require_admin)])
def update_host(
    hostname: str, body: HostUpdateIn, conn: Connection = Depends(db_conn)
) -> dict:
    _get_or_404(conn, hostname)
    fields = body.model_dump(
        exclude_unset=True,
        exclude={"token", "clear_token", "regenerate_ssh_key", "clear_ssh_key"},
    )
    if body.token:
        fields["token_enc"] = _encrypt_or_400(body.token, "the forge token")
    elif body.clear_token:
        fields["token_enc"] = None
    if body.regenerate_ssh_key:
        private_key, public_key = sshkeys.generate_keypair(f"handler@{hostname}")
        fields["ssh_public_key"] = public_key
        fields["ssh_private_key_enc"] = _encrypt_or_400(private_key, "the SSH private key")
    elif body.clear_ssh_key:
        fields["ssh_public_key"] = None
        fields["ssh_private_key_enc"] = None
    return _public(repo.update_host(conn, hostname, **fields))


@router.delete("/{hostname}", dependencies=[Depends(require_admin)])
def delete_host(hostname: str, conn: Connection = Depends(db_conn)) -> dict:
    _get_or_404(conn, hostname)
    repo.delete_host(conn, hostname)
    return {"deleted": hostname}
