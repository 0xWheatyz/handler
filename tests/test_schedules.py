"""Recurring agent spawns: the schedules API and the worker sweep that turns due
schedules into queued ``spawn`` commands with timestamped agent names."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from handler.control import worker
from handler.db import repository as repo
from handler.db.engine import get_engine


def _project(client, auth, tmp_path, project_id="p"):
    root = tmp_path / project_id
    root.mkdir(exist_ok=True)
    r = client.post(
        "/projects", json={"id": project_id, "root_dir": str(root)}, headers=auth
    )
    assert r.status_code == 201, r.text


CONTINUE_TASK = "Read @notes.md, continue from there; before finishing, overwrite that file."


def test_schedule_crud(client, auth, env, tmp_path):
    _project(client, auth, tmp_path)

    r = client.post(
        "/projects/p/schedules",
        json={"name_prefix": "nightly", "task": CONTINUE_TASK, "interval_seconds": 3600},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    sched = r.json()
    assert sched["enabled"] is True
    assert sched["task"] == CONTINUE_TASK
    # First run fires on the worker's next pass.
    next_run = datetime.fromisoformat(sched["next_run_at"])
    assert next_run <= datetime.now(UTC) + timedelta(seconds=5)

    assert client.get("/schedules", headers=auth).json()[0]["id"] == sched["id"]
    assert client.get("/projects/p/schedules", headers=auth).json()[0]["id"] == sched["id"]

    r = client.patch(
        f"/schedules/{sched['id']}",
        json={"interval_seconds": 60, "enabled": False},
        headers=auth,
    )
    assert r.json()["interval_seconds"] == 60
    assert r.json()["enabled"] is False

    r = client.delete(f"/schedules/{sched['id']}", headers=auth)
    assert r.status_code == 200
    assert client.get("/schedules", headers=auth).json() == []


def test_schedule_unknown_project_404(client, auth, env):
    r = client.post(
        "/projects/ghost/schedules",
        json={"name_prefix": "x", "task": "t", "interval_seconds": 60},
        headers=auth,
    )
    assert r.status_code == 404


def test_schedule_validation_422(client, auth, env, tmp_path):
    _project(client, auth, tmp_path)
    r = client.post(
        "/projects/p/schedules",
        json={"name_prefix": "", "task": "t", "interval_seconds": 60},
        headers=auth,
    )
    assert r.status_code == 422
    r = client.post(
        "/projects/p/schedules",
        json={"name_prefix": "x", "task": "t", "interval_seconds": 1},
        headers=auth,
    )
    assert r.status_code == 422


def test_fire_due_schedules_enqueues_spawn(env, tmp_path):
    now = datetime.now(UTC)
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", root_dir=str(tmp_path))
        sched = repo.create_schedule(
            conn,
            project_id="p",
            name_prefix="nightly",
            task=CONTINUE_TASK,
            interval_seconds=3600,
            next_run_at=now - timedelta(seconds=1),
            role="junior",
        )

    assert worker.fire_due_schedules(now) == 1

    with get_engine().begin() as conn:
        commands = repo.list_commands(conn)
        advanced = repo.get_schedule(conn, sched["id"])

    assert len(commands) == 1
    cmd = commands[0]
    assert cmd["type"] == "spawn"
    assert cmd["project_id"] == "p"
    assert cmd["agent_name"].startswith("nightly-")
    assert cmd["payload"]["task"] == CONTINUE_TASK
    assert cmd["payload"]["role"] == "junior"
    assert cmd["requested_by"] == f"schedule:{sched['id']}"

    # The schedule advanced: it will not re-fire until the next interval.
    assert advanced["last_run_at"] is not None
    assert advanced["next_run_at"] > now
    assert advanced["last_command_id"] == cmd["id"]
    assert worker.fire_due_schedules(now) == 0


def test_fire_skips_disabled_and_future(env, tmp_path):
    now = datetime.now(UTC)
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", root_dir=str(tmp_path))
        repo.create_schedule(
            conn, project_id="p", name_prefix="off", task="t",
            interval_seconds=60, next_run_at=now - timedelta(seconds=1), enabled=False,
        )
        repo.create_schedule(
            conn, project_id="p", name_prefix="later", task="t",
            interval_seconds=60, next_run_at=now + timedelta(hours=1),
        )
    assert worker.fire_due_schedules(now) == 0


def test_missed_intervals_collapse_into_one_run(env, tmp_path):
    """A worker that was down for hours fires once, not once per missed interval."""
    now = datetime.now(UTC)
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", root_dir=str(tmp_path))
        sched = repo.create_schedule(
            conn, project_id="p", name_prefix="hourly", task="t",
            interval_seconds=3600, next_run_at=now - timedelta(hours=10),
        )
    assert worker.fire_due_schedules(now) == 1
    with get_engine().begin() as conn:
        advanced = repo.get_schedule(conn, sched["id"])
    assert advanced["next_run_at"] == now + timedelta(hours=1)
    assert worker.fire_due_schedules(now) == 0
