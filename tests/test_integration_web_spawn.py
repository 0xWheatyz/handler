"""End-to-end web management: the dashboard's HTTP calls -> command queue -> worker ->
real ``spawn.spawn`` -> a real headless subprocess (the fake claude binary). Proves the
full container-split flow works with only the claude binary faked, not the control
layer: events stream into the DB, the run reconciles, kill cancels."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from handler.control import worker
from handler.db import repository as repo
from handler.db.engine import get_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_CLAUDE = str(REPO_ROOT / "tests" / "fixtures" / "fake_claude.py")


@pytest.fixture
def headless_env(env, monkeypatch):
    from handler import config

    monkeypatch.setenv("CLAUDE_BIN", FAKE_CLAUDE)
    config.get_settings.cache_clear()
    yield env
    config.get_settings.cache_clear()


def _spawnable_project(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / ".mise.toml").write_text("[tasks.test]\nrun = 'pytest'\n")
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", str(root))


def _wait(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    return None


def test_spawn_via_api_then_worker_runs_headless_claude(client, auth, headless_env):
    _spawnable_project(headless_env["tmp"] / "proj")

    # 1. The dashboard enqueues a spawn (202 + a queued command). A task is mandatory —
    #    headless claude has no idle-REPL mode.
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

    # 2. The control worker drains the queue (real spawn.spawn -> real subprocess).
    assert worker.drain("test-worker") == 1

    # 3. The command finished at launch (fire-and-forget)...
    got = client.get(f"/commands/{command_id}", headers=auth).json()
    assert got["status"] == "done"
    assert got["result"]["name"] == "api"

    # ...and the run's whole life shows up via the API: events stream in, the agent
    # reconciles to done, last_output is the assistant's text.
    def finished():
        agents = client.get("/projects/proj/agents", headers=auth).json()
        return agents if agents and agents[0]["status"] == "done" else None

    agents = _wait(finished)
    assert agents is not None, "run never reconciled to done"
    agent = agents[0]
    assert agent["name"] == "api"
    assert agent["session_id"]
    assert agent["worker_id"] == "test-worker"
    assert agent["last_output"] == "working on: build the thing"

    events = client.get("/projects/proj/agents/api/events", headers=auth).json()
    assert [e["type"] for e in events] == ["system", "assistant", "result"]


def test_spawn_without_task_is_rejected(client, auth, headless_env):
    _spawnable_project(headless_env["tmp"] / "proj")
    r = client.post("/projects/proj/agents/spawn", json={"name": "api"}, headers=auth)
    assert r.status_code == 400
    assert "task is required" in r.json()["detail"]


def test_kill_via_api_then_worker(client, auth, headless_env, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")
    _spawnable_project(headless_env["tmp"] / "proj")
    client.post(
        "/projects/proj/agents/spawn", json={"name": "api", "task": "hang"}, headers=auth
    )
    worker.drain("w")

    # The hanging run is live; kill flags it and the supervisor SIGTERMs its child.
    r = client.post("/projects/proj/agents/api/kill", headers=auth)
    assert r.status_code == 202
    worker.drain("w")

    assert client.get(f"/commands/{r.json()['id']}", headers=auth).json()["status"] == "done"
    with get_engine().begin() as conn:
        agent = repo.get_agent_by_name(conn, "proj", "api")
    assert agent["status"] == "done"

    def canceled():
        with get_engine().begin() as conn:
            run = repo.get_latest_run(conn, agent["id"])
        return run if run["status"] != "running" else None

    run = _wait(canceled, timeout=30.0)
    assert run is not None, "kill never terminated the hanging run"
    assert run["status"] == "canceled"
