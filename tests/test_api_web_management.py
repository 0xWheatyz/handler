"""Web-management API surface: project/host CRUD, enqueue endpoints, and admin gating.

The conftest sets AUTH_TOKEN=test-token and SHARED_CONTEXT_WRITE_TOKEN=shared-token with no
ADMIN_TOKEN, so the effective admin token is the global test-token. The shared-token is a
valid-but-not-admin bearer: it passes require_auth (reads) but not require_admin (writes),
which is exactly what we use to prove the gate."""

from __future__ import annotations

import pytest


@pytest.fixture
def lowpriv(env):
    """A valid bearer that is NOT the admin token (the shared-context write token)."""
    return {"Authorization": f"Bearer {env['shared_token']}"}


def _mk_project(client, auth, pid="proj"):
    return client.post("/projects", json={"id": pid, "root_dir": "/tmp/proj"}, headers=auth)


# --- project CRUD ---------------------------------------------------------------------


def test_get_update_delete_project(client, auth):
    _mk_project(client, auth)
    assert client.get("/projects/proj", headers=auth).json()["id"] == "proj"

    remote = "https://github.com/me/p.git"
    r = client.patch("/projects/proj", json={"git_remote": remote}, headers=auth)
    assert r.status_code == 200 and r.json()["git_remote"] == remote

    assert client.delete("/projects/proj", headers=auth).status_code == 200
    assert client.get("/projects/proj", headers=auth).status_code == 404


def test_credential_ref_cmd_scheme_rejected(client, auth):
    r = client.post(
        "/projects",
        json={"id": "x", "root_dir": "/tmp/x", "credential_ref": "cmd:cat /etc/passwd"},
        headers=auth,
    )
    assert r.status_code == 422
    # env:/file:/db: are accepted.
    ok = client.post(
        "/projects",
        json={"id": "y", "root_dir": "/tmp/y", "credential_ref": "env:TOK"},
        headers=auth,
    )
    assert ok.status_code == 201


def test_patch_project_cmd_scheme_rejected(client, auth):
    _mk_project(client, auth)
    r = client.patch("/projects/proj", json={"credential_ref": "cmd:whoami"}, headers=auth)
    assert r.status_code == 422


# --- admin gating ---------------------------------------------------------------------


def test_reads_allowed_but_writes_need_admin(client, auth, lowpriv):
    _mk_project(client, auth)
    # low-priv token can read...
    assert client.get("/projects", headers=lowpriv).status_code == 200
    assert client.get("/hosts", headers=lowpriv).status_code == 200
    # ...but not perform admin actions.
    patch = client.patch("/projects/proj", json={"root_dir": "/x"}, headers=lowpriv)
    assert patch.status_code == 403
    assert client.delete("/projects/proj", headers=lowpriv).status_code == 403
    host = client.post("/hosts", json={"hostname": "h", "forge_type": "gitea"}, headers=lowpriv)
    assert host.status_code == 403
    spawn = client.post("/projects/proj/agents/spawn", json={"name": "j"}, headers=lowpriv)
    assert spawn.status_code == 403


# --- enqueue endpoints ----------------------------------------------------------------


def test_spawn_enqueues_command(client, auth):
    _mk_project(client, auth)
    r = client.post(
        "/projects/proj/agents/spawn",
        json={"name": "junior", "role": "junior", "worktree": "feat/x", "task": "do it"},
        headers=auth,
    )
    assert r.status_code == 202
    body = r.json()
    assert body["type"] == "spawn" and body["status"] == "queued"
    assert body["agent_name"] == "junior"
    assert body["payload"]["role"] == "junior" and body["payload"]["worktree"] == "feat/x"
    # visible on the commands feed
    assert any(c["id"] == body["id"] for c in client.get("/commands", headers=auth).json())


def test_kill_enqueues_command(client, auth):
    _mk_project(client, auth)
    client.post(
        "/projects/proj/agents",
        json={"name": "api", "working_dir": "/tmp/proj/api"},
        headers=auth,
    )
    r = client.post("/projects/proj/agents/api/kill", headers=auth)
    assert r.status_code == 202 and r.json()["type"] == "kill"


def test_approval_enqueues_correct_command_type(client, auth):
    _mk_project(client, auth)
    r = client.post(
        "/projects/proj/approvals",
        json={"branch": "feat/x", "status": "rejected", "note": "nit"},
        headers=auth,
    )
    assert r.status_code == 202
    # verdict 'rejected' maps to command type 'reject'
    assert r.json()["type"] == "reject"
    assert r.json()["payload"]["branch"] == "feat/x"


def test_forge_init_and_poll_ci_enqueue(client, auth):
    _mk_project(client, auth)
    assert client.post("/projects/proj/forge-init", headers=auth).json()["type"] == "forge_init"
    assert client.post("/projects/proj/poll-ci", headers=auth).json()["type"] == "poll_ci"
    assert client.post("/poll-ci", headers=auth).json()["project_id"] is None


def test_command_status_polling(client, auth):
    _mk_project(client, auth)
    cmd = client.post("/projects/proj/poll-ci", headers=auth).json()
    got = client.get(f"/commands/{cmd['id']}", headers=auth)
    assert got.status_code == 200 and got.json()["id"] == cmd["id"]
    assert client.get("/commands/999999", headers=auth).status_code == 404


# --- hosts ----------------------------------------------------------------------------


def test_host_crud(client, auth):
    r = client.post(
        "/hosts",
        json={"hostname": "git.corp", "forge_type": "gitea", "token_env_var": "GITEA_TOKEN"},
        headers=auth,
    )
    assert r.status_code == 201
    assert client.get("/hosts/git.corp", headers=auth).json()["token_env_var"] == "GITEA_TOKEN"
    patch = client.patch("/hosts/git.corp", json={"base_url": "https://git.corp"}, headers=auth)
    assert patch.status_code == 200
    assert client.delete("/hosts/git.corp", headers=auth).status_code == 200
    assert client.get("/hosts/git.corp", headers=auth).status_code == 404


def test_host_bad_forge_type_422(client, auth):
    r = client.post("/hosts", json={"hostname": "h", "forge_type": "svn"}, headers=auth)
    assert r.status_code == 422
