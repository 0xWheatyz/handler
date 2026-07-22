"""Slot-aware command claiming: a worker at max_concurrent_runs must leave run-starting
commands queued (for a less-loaded worker) while still processing everything else. Slot
accounting is DB-driven — this worker's ``running`` agent_runs rows — so it needs no
in-memory registry and is exercised here without real subprocesses."""

from __future__ import annotations

import pytest

from handler.control import spawn, worker
from handler.db import repository as repo
from handler.db.engine import get_engine


@pytest.fixture
def headless_env(env, monkeypatch):
    from handler import config

    monkeypatch.setenv("MAX_CONCURRENT_RUNS", "2")
    config.get_settings.cache_clear()
    yield env
    config.get_settings.cache_clear()


def _seed(extra_agents=("b",)):
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", "/tmp/p")
        agent = repo.create_agent(conn, "p", "a", "/tmp/p/a")
        for name in extra_agents:
            repo.create_agent(conn, "p", name, f"/tmp/p/{name}")
        return agent


def _running_run(agent_name, worker_id):
    with get_engine().begin() as conn:
        agent = repo.get_agent_by_name(conn, "p", agent_name)
        return repo.create_run(conn, agent["id"], f"sid-{agent_name}", worker_id, "spawn")


def test_full_worker_skips_run_commands_but_processes_others(headless_env, monkeypatch):
    agent = _seed()
    # 2 running (one per agent — one running run per agent) == MAX_CONCURRENT_RUNS
    _running_run("a", "w-full")
    _running_run("b", "w-full")

    spawned = {}
    monkeypatch.setattr(
        spawn, "spawn",
        lambda project_id, name, **kw: spawned.update(name=name, **kw)
        or {"id": 1, "name": name, "working_dir": "/tmp/p/x", "forge_note": None},
    )
    with get_engine().begin() as conn:
        spawn_cmd = repo.enqueue_command(conn, "spawn", project_id="p", agent_name="x")
        kill_cmd = repo.enqueue_command(conn, "kill", project_id="p", agent_name="a")
    monkeypatch.setattr(spawn, "kill", lambda p, n: None)

    # The full worker processes the kill but leaves the spawn queued.
    assert worker.drain("w-full") == 1
    with get_engine().begin() as conn:
        assert repo.get_command(conn, kill_cmd["id"])["status"] == "done"
        assert repo.get_command(conn, spawn_cmd["id"])["status"] == "queued"
    assert spawned == {}

    # A worker with free slots picks the spawn up.
    assert worker.drain("w-free") == 1
    with get_engine().begin() as conn:
        assert repo.get_command(conn, spawn_cmd["id"])["status"] == "done"
    assert spawned["name"] == "x"
    assert spawned["worker_id"] == "w-free"


def test_slot_frees_when_run_finishes(headless_env, monkeypatch):
    _seed()
    run1 = _running_run("a", "w1")
    _running_run("b", "w1")
    assert worker._full_slot_exclusions("w1") == worker._RUN_COMMANDS

    with get_engine().begin() as conn:
        repo.finish_run(conn, run1["id"], "completed", exit_code=0)
    assert worker._full_slot_exclusions("w1") == ()
