"""Shared-context + shared-log endpoints and the write-token gate."""

from __future__ import annotations

from handler.db import repository as repo
from handler.db.engine import get_engine


def test_put_shared_context_requires_write_token(client, auth, env):
    # The normal token is not enough to write shared context.
    r = client.put("/shared/context/schema_version", json={"value": "v3"}, headers=auth)
    assert r.status_code == 403

    write_headers = {"Authorization": f"Bearer {env['shared_token']}"}
    r = client.put(
        "/shared/context/schema_version", json={"value": "v3"}, headers=write_headers
    )
    assert r.status_code == 200
    assert r.json()["value"] == "v3"


def test_read_shared_context_uses_normal_token(client, auth, env):
    write_headers = {"Authorization": f"Bearer {env['shared_token']}"}
    client.put("/shared/context/k", json={"value": "v"}, headers=write_headers)

    assert client.get("/shared/context", headers=auth).status_code == 200
    assert client.get("/shared/context/k", headers=auth).json()["value"] == "v"
    assert client.get("/shared/context/missing", headers=auth).status_code == 404


def test_shared_log_returns_only_global(client, auth, env):
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", "/tmp/p")
        a = repo.create_agent(conn, "p", "a", "/tmp/p/a")
        repo.insert_log_entry(conn, a["id"], status="working", summary="private")
        repo.insert_log_entry(
            conn, a["id"], status="working", summary="global-note", visibility="global"
        )
    entries = client.get("/shared/log", headers=auth).json()
    assert [e["summary"] for e in entries] == ["global-note"]
