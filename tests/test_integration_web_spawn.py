"""End-to-end web management: the dashboard's HTTP calls -> command queue -> worker ->
real ``spawn.spawn`` -> tmux seam. Proves the full container-split flow works with only the
tmux/claude boundary faked, not the control layer itself."""

from __future__ import annotations

from handler.control import worker
from handler.db import repository as repo
from handler.db.engine import get_engine


def _spawnable_project(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / ".mise.toml").write_text("[tasks.test]\nrun = 'pytest'\n")
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", str(root))


def test_spawn_via_api_then_worker_creates_agent_and_session(client, auth, env, fake_tmux):
    _spawnable_project(env["tmp"] / "proj")

    # 1. The dashboard enqueues a spawn (202 + a queued command).
    r = client.post(
        "/projects/proj/agents/spawn",
        json={"name": "api", "task": "build the thing"},
        headers=auth,
    )
    assert r.status_code == 202
    command_id = r.json()["id"]
    assert r.json()["status"] == "queued"

    # No agent yet — the worker hasn't run.
    assert client.get("/projects/proj/agents", headers=auth).json() == []

    # 2. The control worker drains the queue (runs the real spawn.spawn).
    assert worker.drain("test-worker") == 1

    # 3. The command is done and the agent + tmux session now exist.
    got = client.get(f"/commands/{command_id}", headers=auth).json()
    assert got["status"] == "done"
    assert got["result"]["name"] == "api"

    agents = client.get("/projects/proj/agents", headers=auth).json()
    assert [a["name"] for a in agents] == ["api"]
    assert fake_tmux["calls"]["new_session"][0]["name"] == "proj__api"


def test_kill_via_api_then_worker(client, auth, env, fake_tmux):
    _spawnable_project(env["tmp"] / "proj")
    client.post("/projects/proj/agents/spawn", json={"name": "api"}, headers=auth)
    worker.drain("w")

    r = client.post("/projects/proj/agents/api/kill", headers=auth)
    assert r.status_code == 202
    worker.drain("w")

    assert client.get(f"/commands/{r.json()['id']}", headers=auth).json()["status"] == "done"
    assert "proj__api" in fake_tmux["calls"]["kill_session"]
    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "proj", "api")["status"] == "done"
