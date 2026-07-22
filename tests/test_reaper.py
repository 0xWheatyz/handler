"""Worker heartbeat + reaper: a worker that stops heartbeating gets its running runs
(and their still-'working' agents) marked crashed by any surviving worker — the positive
liveness that replaces tmux scraping. No auto-requeue: half-done runs may have pushed."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from handler.control import worker
from handler.db import repository as repo
from handler.db.engine import get_engine


def _seed_run(worker_id, agent_name="a", agent_status="working"):
    with get_engine().begin() as conn:
        if repo.get_project(conn, "p") is None:
            repo.create_project(conn, "p", "/tmp/p")
        agent = repo.create_agent(conn, "p", agent_name, f"/tmp/p/{agent_name}",
                                  status=agent_status)
        run = repo.create_run(conn, agent["id"], f"sid-{agent_name}", worker_id, "spawn")
    return agent, run


def _hb(worker_id, age_seconds=0.0):
    with get_engine().begin() as conn:
        repo.upsert_worker_heartbeat(conn, worker_id, hostname="h", pid=1)
        if age_seconds:
            from handler.db.tables import workers as workers_table

            conn.execute(
                workers_table.update()
                .where(workers_table.c.id == worker_id)
                .values(heartbeat_at=datetime.now(UTC) - timedelta(seconds=age_seconds))
            )


def test_reaper_marks_stale_workers_runs_crashed(env):
    agent, run = _seed_run("w-dead")
    _hb("w-dead", age_seconds=120)  # stale: default worker_stale_after is 60s

    assert worker.reap_dead_workers() == 1

    with get_engine().begin() as conn:
        assert repo.get_run(conn, run["id"])["status"] == "crashed"
        assert repo.get_agent_by_id(conn, agent["id"])["status"] == "crashed"
        events = repo.list_agent_events(conn, agent["id"])
        # The dead worker's registry row is dropped once settled.
        assert repo.list_stale_workers(conn, datetime.now(UTC) + timedelta(days=1)) == []
    assert events[0]["type"] == "worker"
    assert events[0]["payload"]["worker_id"] == "w-dead"


def test_reaper_leaves_fresh_workers_alone(env):
    agent, run = _seed_run("w-live")
    _hb("w-live")  # fresh heartbeat

    assert worker.reap_dead_workers() == 0
    with get_engine().begin() as conn:
        assert repo.get_run(conn, run["id"])["status"] == "running"
        assert repo.get_agent_by_id(conn, agent["id"])["status"] == "working"


def test_reaper_preserves_paused_agent_status(env):
    """paused_for_input still accurately describes what the agent needs — only agents
    stuck in 'working' get flipped to crashed."""
    agent, run = _seed_run("w-dead2", agent_name="paused", agent_status="paused_for_input")
    _hb("w-dead2", age_seconds=120)

    assert worker.reap_dead_workers() == 1
    with get_engine().begin() as conn:
        assert repo.get_run(conn, run["id"])["status"] == "crashed"
        assert repo.get_agent_by_id(conn, agent["id"])["status"] == "paused_for_input"


def test_reaper_idempotent_against_races(env):
    agent, run = _seed_run("w-dead3", agent_name="raced")
    _hb("w-dead3", age_seconds=120)
    assert worker.reap_dead_workers() == 1
    # A second reaper (or the same one next pass) finds nothing left to settle.
    assert worker.reap_dead_workers() == 0
    with get_engine().begin() as conn:
        assert len(repo.list_agent_events(conn, agent["id"])) == 1


def test_heartbeat_registers_worker(env):
    worker.heartbeat("w-me")
    with get_engine().begin() as conn:
        rows = repo.list_stale_workers(conn, datetime.now(UTC) + timedelta(seconds=1))
    assert [w["id"] for w in rows] == ["w-me"]
    assert rows[0]["hostname"]
    assert rows[0]["active_runs"] == 0


def test_events_route_serves_stream(env, client, auth):
    agent, run = _seed_run("w-api", agent_name="api-agent")
    with get_engine().begin() as conn:
        for seq in range(1, 4):
            repo.insert_agent_event(
                conn, agent["id"], run["id"], seq=seq, type="assistant",
                payload={"n": seq}, session_id=run["session_id"],
            )

    resp = client.get("/projects/p/agents/api-agent/events", headers=auth)
    assert resp.status_code == 200
    events = resp.json()
    assert [e["seq"] for e in events] == [1, 2, 3]
    assert events[0]["type"] == "assistant"

    # Cursor paging: only events after the given id come back.
    resp = client.get(
        f"/projects/p/agents/api-agent/events?after_id={events[1]['id']}", headers=auth
    )
    assert [e["seq"] for e in resp.json()] == [3]

    resp = client.get("/projects/p/agents/missing/events", headers=auth)
    assert resp.status_code == 404
