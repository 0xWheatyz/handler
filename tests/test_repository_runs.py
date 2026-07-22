"""Repository coverage for the headless-runner tables (workers / agent_runs /
agent_events / session_archives) and the new claim filters. The ``env`` fixture runs the
real ``alembic upgrade head``, so migration 0008 itself is under test here too."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from handler.db import repository as repo


def _agent(conn, name="a1"):
    repo.create_project(conn, "p", "/projects/p")
    return repo.create_agent(conn, "p", name, "/projects/p")


# ------------------------------------------------------------------------ agent_runs


def test_run_lifecycle(conn):
    agent = _agent(conn)
    run = repo.create_run(conn, agent["id"], "sid-1", "worker-a", "spawn")
    assert run["status"] == "running"
    assert run["kind"] == "spawn"
    assert run["cancel_requested"] is False

    assert repo.finish_run(conn, run["id"], "completed", exit_code=0, result={"ok": True})
    done = repo.get_run(conn, run["id"])
    assert done["status"] == "completed"
    assert done["exit_code"] == 0
    assert done["result"] == {"ok": True}
    assert done["finished_at"] is not None


def test_finish_run_only_once(conn):
    """The supervisor's verdict and a racing reaper can't clobber each other."""
    agent = _agent(conn)
    run = repo.create_run(conn, agent["id"], "sid", "w", "spawn")
    assert repo.finish_run(conn, run["id"], "crashed") is True
    assert repo.finish_run(conn, run["id"], "completed", exit_code=0) is False
    assert repo.get_run(conn, run["id"])["status"] == "crashed"


def test_cancel_request_roundtrip(conn):
    agent = _agent(conn)
    run = repo.create_run(conn, agent["id"], "sid", "w", "resume")
    assert repo.get_cancel_requested(conn, run["id"]) is False
    assert repo.request_run_cancel(conn, run["id"]) is True
    assert repo.get_cancel_requested(conn, run["id"]) is True
    # A finished run can't be re-flagged.
    repo.finish_run(conn, run["id"], "canceled")
    assert repo.request_run_cancel(conn, run["id"]) is False


def test_list_running_runs_scoped_by_worker(conn):
    agent = _agent(conn)
    r1 = repo.create_run(conn, agent["id"], "s1", "worker-a", "spawn")
    repo.finish_run(conn, r1["id"], "completed")
    r2 = repo.create_run(conn, agent["id"], "s2", "worker-b", "spawn")
    running = repo.list_running_runs(conn)
    assert [r["id"] for r in running] == [r2["id"]]
    assert repo.list_running_runs(conn, worker_id="worker-a") == []
    assert [r["id"] for r in repo.list_running_runs(conn, worker_id="worker-b")] == [r2["id"]]


def test_create_run_refuses_concurrent_run_for_agent(conn):
    """One running run per agent, atomically — two workers racing a resume must not both
    launch a claude process on the same session."""
    import pytest

    agent = _agent(conn)
    repo.create_run(conn, agent["id"], "s1", "worker-a", "spawn")
    with pytest.raises(repo.RunConflictError):
        repo.create_run(conn, agent["id"], "s1", "worker-b", "resume")


def test_latest_run_and_agent_session(conn):
    agent = _agent(conn)
    first = repo.create_run(conn, agent["id"], "s1", "w", "spawn")
    repo.finish_run(conn, first["id"], "completed")
    latest = repo.create_run(conn, agent["id"], "s1", "w", "resume")
    assert repo.get_latest_run(conn, agent["id"])["id"] == latest["id"]

    repo.set_agent_session(conn, agent["id"], "s1", "worker-a")
    updated = repo.get_agent_by_id(conn, agent["id"])
    assert updated["session_id"] == "s1"
    assert updated["worker_id"] == "worker-a"


def test_agent_status_crashed_allowed(conn):
    """Migration 0008 widened ck_agents_status — 'crashed' must insert cleanly."""
    agent = _agent(conn)
    repo.set_agent_status(conn, agent["id"], "crashed")
    assert repo.get_agent_by_id(conn, agent["id"])["status"] == "crashed"


# ---------------------------------------------------------------------- agent_events


def test_events_cursor_pagination(conn):
    agent = _agent(conn)
    run = repo.create_run(conn, agent["id"], "sid", "w", "spawn")
    for seq in range(1, 4):
        repo.insert_agent_event(
            conn, agent["id"], run["id"], seq=seq, type="assistant",
            payload={"n": seq}, session_id="sid",
        )
    first = repo.list_agent_events(conn, agent["id"], limit=2)
    assert [e["payload"]["n"] for e in first] == [1, 2]
    rest = repo.list_agent_events(conn, agent["id"], after_id=first[-1]["id"])
    assert [e["payload"]["n"] for e in rest] == [3]
    assert repo.list_agent_events(conn, agent["id"], after_id=rest[-1]["id"]) == []


# ------------------------------------------------------------------ session_archives


def test_session_archive_upsert_replaces(conn):
    agent = _agent(conn)
    repo.upsert_session_archive(conn, agent["id"], "s1", b"v1")
    repo.upsert_session_archive(conn, agent["id"], "s2", b"v2-longer")
    row = repo.get_session_archive(conn, agent["id"])
    assert row["session_id"] == "s2"
    assert bytes(row["archive"]) == b"v2-longer"
    assert row["bytes"] == len(b"v2-longer")


def test_session_archive_missing(conn):
    agent = _agent(conn)
    assert repo.get_session_archive(conn, agent["id"]) is None


# ------------------------------------------------------------------------- workers


def test_worker_heartbeat_upsert_and_staleness(conn):
    repo.upsert_worker_heartbeat(conn, "worker-a", hostname="h1", pid=42, max_runs=4)
    repo.upsert_worker_heartbeat(conn, "worker-a", hostname="h1", pid=42, active_runs=2)

    future = datetime.now(UTC) + timedelta(seconds=1)
    stale = repo.list_stale_workers(conn, cutoff=future)
    assert [w["id"] for w in stale] == ["worker-a"]
    assert stale[0]["active_runs"] == 2

    past = datetime.now(UTC) - timedelta(minutes=5)
    assert repo.list_stale_workers(conn, cutoff=past) == []


# ------------------------------------------------------------------- claim filters


def test_claim_respects_target_worker(conn):
    repo.create_project(conn, "p", "/projects/p")
    pinned = repo.enqueue_command(conn, "login_submit", payload={"code": "x"},
                                  target_worker="worker-b")
    # worker-a can't see worker-b's pinned command...
    assert repo.claim_next_command(conn, "worker-a") is None
    # ...but worker-b claims it.
    claimed = repo.claim_next_command(conn, "worker-b")
    assert claimed["id"] == pinned["id"]
    assert claimed["status"] == "running"


def test_claim_excludes_types_when_slots_full(conn):
    repo.create_project(conn, "p", "/projects/p")
    spawn_cmd = repo.enqueue_command(conn, "spawn", project_id="p", agent_name="a")
    sync_cmd = repo.enqueue_command(conn, "sync", project_id="p")
    # With run-starting types excluded, the older spawn is skipped for the sync.
    claimed = repo.claim_next_command(
        conn, "w", types_excluded=("spawn", "resume", "mise_init")
    )
    assert claimed["id"] == sync_cmd["id"]
    # The spawn stays queued for a worker with a free slot.
    assert repo.claim_next_command(conn, "w2")["id"] == spawn_cmd["id"]


def test_delete_agent_cascades_headless_rows(conn):
    agent = _agent(conn)
    run = repo.create_run(conn, agent["id"], "sid", "w", "spawn")
    repo.insert_agent_event(conn, agent["id"], run["id"], seq=1, type="system", payload={})
    repo.upsert_session_archive(conn, agent["id"], "sid", b"data")

    assert repo.delete_agent(conn, "p", agent["name"]) is True
    assert repo.get_latest_run(conn, agent["id"]) is None
    assert repo.list_agent_events(conn, agent["id"]) == []
    assert repo.get_session_archive(conn, agent["id"]) is None
