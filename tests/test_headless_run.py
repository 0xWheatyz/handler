"""End-to-end headless runner tests against the fake ``claude`` binary.

Real subprocesses, real threads, real SQLite: ``headless.launch`` starts
``tests/fixtures/fake_claude.py`` (selected via the ``claude_bin`` setting, the same
seam the tmux fakes used), the supervisor streams its stdout into ``agent_events``, and
the tests assert on what landed in the DB — exactly what the API/UI will read."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from handler.control import headless, settings_gen, spawn
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


def _make_agent(tmp_path, name="h1"):
    working_dir = tmp_path / "projects" / "p" / name
    working_dir.mkdir(parents=True)
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", str(tmp_path / "projects" / "p"))
        agent = repo.create_agent(conn, "p", name, str(working_dir))
    return agent


def _wait_for(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    return None


def _finished_run(run_id):
    def check():
        with get_engine().begin() as conn:
            run = repo.get_run(conn, run_id)
        return run if run["status"] != "running" else None

    return check


def test_spawn_run_streams_events_and_completes(headless_env, tmp_path):
    agent = _make_agent(tmp_path)
    run = headless.launch(
        agent, kind="spawn", prompt="build the thing",
        settings_path=str(tmp_path / "settings.json"), env={}, worker_id="w1",
    )
    finished = _wait_for(_finished_run(run["id"]))
    assert finished is not None, "run never finished"
    assert finished["status"] == "completed"
    assert finished["exit_code"] == 0
    assert finished["result"]["is_error"] is False

    with get_engine().begin() as conn:
        events = repo.list_agent_events(conn, agent["id"])
        updated = repo.get_agent_by_id(conn, agent["id"])
        archive = repo.get_session_archive(conn, agent["id"])

    types = [e["type"] for e in events]
    assert types == ["system", "assistant", "result"]
    assert [e["seq"] for e in events] == [1, 2, 3]
    # last_output is now derived from assistant text — the log the UI shows is real.
    assert updated["last_output"] == "working on: build the thing"
    # done is a gate outcome, not an exit code: the fake claude never ran the Stop
    # hook, so nothing verified tests/commits/pushes and the agent must not be done.
    assert updated["status"] == "blocked"
    assert updated["session_id"] == run["session_id"]
    assert updated["worker_id"] == "w1"
    # The session archive was uploaded at exit for cross-worker resume.
    assert archive is not None
    assert archive["session_id"] == run["session_id"]


def test_failed_run_marks_blocked_with_worker_event(headless_env, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "error")
    agent = _make_agent(tmp_path, "h-err")
    run = headless.launch(
        agent, kind="spawn", prompt="boom",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="w1",
    )
    finished = _wait_for(_finished_run(run["id"]))
    assert finished["status"] == "failed"
    assert finished["exit_code"] == 2

    with get_engine().begin() as conn:
        events = repo.list_agent_events(conn, agent["id"])
        updated = repo.get_agent_by_id(conn, agent["id"])
    types = [e["type"] for e in events]
    # The unparseable stdout line is preserved verbatim as a raw event, and the runner
    # records why the run failed as a worker event.
    assert "raw" in types
    raw = next(e for e in events if e["type"] == "raw")
    assert "this is not json" in raw["payload"]["line"]
    worker_ev = next(e for e in events if e["type"] == "worker")
    assert worker_ev["payload"]["exit_code"] == 2
    assert updated["status"] == "blocked"


def test_hook_written_status_survives_reconciliation(headless_env, tmp_path, monkeypatch):
    """Hooks are the status authority: if one set paused_for_input during the run, the
    supervisor's exit pass must not overwrite it with done."""
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "slow")
    monkeypatch.setenv("FAKE_CLAUDE_SLOW_SECONDS", "1.5")
    agent = _make_agent(tmp_path, "h-hook")
    run = headless.launch(
        agent, kind="spawn", prompt="ask me something",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="w1",
    )
    # Simulate a hook (inside the run) recording an open question.
    with get_engine().begin() as conn:
        repo.set_agent_status(conn, agent["id"], "paused_for_input")
    finished = _wait_for(_finished_run(run["id"]))
    assert finished["status"] == "completed"
    with get_engine().begin() as conn:
        assert repo.get_agent_by_id(conn, agent["id"])["status"] == "paused_for_input"


def test_cancel_terminates_hanging_run(headless_env, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")
    agent = _make_agent(tmp_path, "h-hang")
    run = headless.launch(
        agent, kind="spawn", prompt="hang forever",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="w1",
    )
    # Give the supervisor a moment to start the process, then flag the cancel the same
    # way a cross-worker kill would.
    _wait_for(lambda: _events_count(agent["id"]) >= 1)
    with get_engine().begin() as conn:
        assert repo.request_run_cancel(conn, run["id"]) is True
    finished = _wait_for(_finished_run(run["id"]), timeout=30.0)
    assert finished is not None, "cancel never terminated the run"
    assert finished["status"] == "canceled"


def _events_count(agent_id):
    with get_engine().begin() as conn:
        return len(repo.list_agent_events(conn, agent_id))


def test_kill_headless_agent_requests_cancel(headless_env, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")
    agent = _make_agent(tmp_path, "h-kill")
    run = headless.launch(
        agent, kind="spawn", prompt="hang",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="w1",
    )
    _wait_for(lambda: _events_count(agent["id"]) >= 1)
    spawn.kill("p", "h-kill")
    finished = _wait_for(_finished_run(run["id"]), timeout=30.0)
    assert finished["status"] == "canceled"
    with get_engine().begin() as conn:
        assert repo.get_agent_by_id(conn, agent["id"])["status"] == "done"


def test_cross_worker_resume_materializes_archive(headless_env, tmp_path, monkeypatch):
    """The linchpin: worker B resumes a session it never ran, from the DB archive alone."""
    agent = _make_agent(tmp_path, "h-resume")
    run = headless.launch(
        agent, kind="spawn", prompt="first pass",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="worker-a",
    )
    assert _wait_for(_finished_run(run["id"]))["status"] == "completed"

    # "Worker B": a clean HOME with no local claude state at all.
    other_home = tmp_path / "worker-b-home"
    other_home.mkdir()
    monkeypatch.setenv("HOME", str(other_home))

    with get_engine().begin() as conn:
        agent = repo.get_agent_by_id(conn, agent["id"])  # refetch: has session_id now
    ok, detail = spawn.resume(agent, "the operator's answer", worker_id="worker-b")
    assert ok, detail

    with get_engine().begin() as conn:
        resumed = repo.get_latest_run(conn, agent["id"])
    assert resumed["kind"] == "resume"
    assert resumed["worker_id"] == "worker-b"
    finished = _wait_for(_finished_run(resumed["id"]))
    # fake_claude exits 3 if the transcript was NOT materialized where claude looks.
    assert finished["status"] == "completed", f"exit={finished['exit_code']}"
    assert finished["session_id"] == run["session_id"]  # same session, continued


def test_resume_without_transcript_reinjects_context(headless_env, tmp_path, monkeypatch):
    """Owning worker died before its first archive: resume degrades to a fresh session
    with DB-rebuilt context, visibly marked as such."""
    agent = _make_agent(tmp_path, "h-fallback")
    with get_engine().begin() as conn:
        repo.set_agent_session(conn, agent["id"], "lost-session-uuid", "worker-dead")
        repo.upsert_checkmark_row(
            conn, agent["id"], status="paused_for_input",
            where_it_stopped="mid-refactor", open_question="which db?",
        )
        agent = repo.get_agent_by_id(conn, agent["id"])

    ok, detail = spawn.resume(agent, "use postgres", worker_id="worker-b")
    assert ok
    assert "re-injected" in detail

    with get_engine().begin() as conn:
        new_run = repo.get_latest_run(conn, agent["id"])
        events = repo.list_agent_events(conn, agent["id"])
    assert new_run["kind"] == "spawn"  # genuinely new session
    assert new_run["session_id"] != "lost-session-uuid"
    notice = next(e for e in events if e["type"] == "worker")
    assert notice["payload"]["previous_session_id"] == "lost-session-uuid"
    finished = _wait_for(_finished_run(new_run["id"]))
    assert finished["status"] == "completed"
    with get_engine().begin() as conn:
        assistant = [
            e for e in repo.list_agent_events(conn, agent["id"]) if e["type"] == "assistant"
        ]
    # The re-injected prompt (with the operator's answer) reached the fresh claude.
    assert any("use postgres" in json.dumps(e["payload"]) for e in assistant)


def test_resume_refused_while_run_live(headless_env, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")
    agent = _make_agent(tmp_path, "h-busy")
    run = headless.launch(
        agent, kind="spawn", prompt="hang",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="w1",
    )
    with get_engine().begin() as conn:
        agent = repo.get_agent_by_id(conn, agent["id"])
    ok, detail = spawn.resume(agent, "answer", worker_id="w1")
    assert not ok
    assert "live run" in detail
    with get_engine().begin() as conn:
        repo.request_run_cancel(conn, run["id"])
    _wait_for(_finished_run(run["id"]), timeout=30.0)


def test_settings_include_permissions_and_hooks(headless_env, tmp_path):
    path = settings_gen.write_settings(str(tmp_path / "wd"))
    data = json.loads(Path(path).read_text())
    assert data["permissions"]["defaultMode"] == "acceptEdits"
    assert "Bash(git *)" in data["permissions"]["allow"]
    assert "hooks" in data  # the hard gate is untouched


def test_api_rejects_empty_task_headless_spawn(headless_env, client, auth):
    client.post(
        "/projects", json={"id": "p2", "root_dir": "/tmp/p2"}, headers=auth
    )
    resp = client.post(
        "/projects/p2/agents/spawn", json={"name": "idle"}, headers=auth
    )
    assert resp.status_code == 400
    assert "task is required" in resp.json()["detail"]
