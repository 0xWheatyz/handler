"""The control worker: command dispatch + the claim/finish plumbing.

Uses the same mock seams as the CLI tests (tmux/gitops/forge/spawn.resume) plus direct
monkeypatching of spawn.spawn/kill so we exercise the worker's routing, not the full spawn
machinery (already covered by test_control_spawn)."""

from __future__ import annotations

from handler.control import login, poller, spawn, worker
from handler.db import repository as repo
from handler.db.engine import get_engine


def _seed_project(agent=None):
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", "/tmp/p")
        if agent:
            repo.create_agent(conn, "p", agent, f"/tmp/p/{agent}", status="paused_for_input")


def _enqueue(**kw):
    with get_engine().begin() as conn:
        return repo.enqueue_command(conn, **kw)


def _get(cmd_id):
    with get_engine().begin() as conn:
        return repo.get_command(conn, cmd_id)


def test_spawn_command_calls_spawn_and_records_result(env, monkeypatch):
    _seed_project()
    calls = {}

    def fake_spawn(project_id, name, **kw):
        calls.update(project_id=project_id, name=name, **kw)
        return {"id": 42, "name": name, "working_dir": "/tmp/p/j", "forge_note": None}

    monkeypatch.setattr(spawn, "spawn", fake_spawn)
    cmd = _enqueue(
        type="spawn", project_id="p", agent_name="j",
        payload={"role": "junior", "worktree": "feat/x"},
    )

    assert worker.drain("w") == 1
    done = _get(cmd["id"])
    assert done["status"] == "done"
    assert done["result"]["agent_id"] == 42
    assert calls["project_id"] == "p" and calls["name"] == "j"
    assert calls["role"] == "junior" and calls["worktree_branch"] == "feat/x"


def test_kill_command_calls_kill(env, monkeypatch):
    _seed_project("api")
    killed = {}
    monkeypatch.setattr(spawn, "kill", lambda p, n: killed.update(project=p, name=n))
    cmd = _enqueue(type="kill", project_id="p", agent_name="api")

    worker.drain("w")
    assert _get(cmd["id"])["status"] == "done"
    assert killed == {"project": "p", "name": "api"}


def test_resume_command_feeds_answer_and_sets_working(env, monkeypatch):
    _seed_project("api")
    seen = {}

    def fake_resume(agent, ans):
        seen.update(name=agent["name"], ans=ans)
        return True, "ok"

    monkeypatch.setattr(spawn, "resume", fake_resume)
    cmd = _enqueue(type="resume", project_id="p", agent_name="api", payload={"answer": "Postgres"})

    worker.drain("w")
    assert _get(cmd["id"])["status"] == "done"
    assert seen == {"name": "api", "ans": "Postgres"}
    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "p", "api")["status"] == "working"


def test_approve_command_records_operator_verdict_with_head_sha(env, fake_gitops):
    _seed_project("senior")
    cmd = _enqueue(
        type="approve", project_id="p", agent_name="senior", payload={"branch": "feat/x"}
    )

    worker.drain("w")
    assert _get(cmd["id"])["status"] == "done"
    with get_engine().begin() as conn:
        ap = repo.get_latest_approval(conn, "p", "feat/x")
    assert ap["status"] == "approved"
    assert ap["actor"] == "operator:web"
    assert ap["approved_by_agent_id"] is None
    assert ap["approved_sha"] == fake_gitops["sha"]  # read from the agent's working dir


def test_mise_init_command_spawns_bootstrap_agent(env, monkeypatch):
    _seed_project()
    calls = {}

    def fake_spawn(project_id, name, **kw):
        calls.update(project_id=project_id, name=name, **kw)
        return {"id": 7, "name": name, "working_dir": "/tmp/p/mise-init"}

    monkeypatch.setattr(spawn, "spawn", fake_spawn)
    cmd = _enqueue(type="mise_init", project_id="p")

    assert worker.drain("w") == 1
    done = _get(cmd["id"])
    assert done["status"] == "done"
    assert done["result"]["agent_id"] == 7
    assert done["result"]["name"] == "mise-init"
    # Launched with the test gate off and the bootstrap marker on, with the default task.
    assert calls["require_tests"] is False
    assert calls["mise_init"] is True
    assert ".mise.toml" in calls["task"]


def test_mise_init_command_honors_payload_overrides(env, monkeypatch):
    _seed_project()
    calls = {}

    def fake_spawn(project_id, name, **kw):
        calls.update(name=name, **kw)
        return {"id": 8, "name": name, "working_dir": "/tmp/p/x"}

    monkeypatch.setattr(spawn, "spawn", fake_spawn)
    cmd = _enqueue(
        type="mise_init", project_id="p", payload={"name": "boot", "task": "custom task"}
    )

    worker.drain("w")
    assert _get(cmd["id"])["status"] == "done"
    assert calls["name"] == "boot"
    assert calls["task"] == "custom task"


def test_mise_init_without_project_is_failed(env):
    cmd = _enqueue(type="mise_init")
    assert worker.drain("w") == 1
    assert _get(cmd["id"])["status"] == "failed"


def test_poll_ci_command_returns_summary(env, monkeypatch):
    _seed_project()
    summary = {"checked": 0, "resolved": 0, "pending": 0}
    monkeypatch.setattr(poller, "sweep", lambda project_id=None: summary)
    cmd = _enqueue(type="poll_ci", project_id="p")

    worker.drain("w")
    done = _get(cmd["id"])
    assert done["status"] == "done"
    assert done["result"] == {"checked": 0, "resolved": 0, "pending": 0}


def test_login_start_command_returns_url(env, monkeypatch):
    monkeypatch.setattr(
        login, "start", lambda: {"session": "handler__login", "url": "https://claude.ai/oauth"}
    )
    cmd = _enqueue(type="login_start")

    worker.drain("w")
    done = _get(cmd["id"])
    assert done["status"] == "done"
    assert done["result"]["url"] == "https://claude.ai/oauth"


def test_login_submit_command_feeds_code(env, monkeypatch):
    seen = {}

    def fake_submit(code):
        seen["code"] = code
        return {"success": True, "output": "Login successful"}

    monkeypatch.setattr(login, "submit_code", fake_submit)
    cmd = _enqueue(type="login_submit", payload={"code": "auth-123"})

    worker.drain("w")
    done = _get(cmd["id"])
    assert done["status"] == "done"
    assert done["result"]["success"] is True
    assert seen["code"] == "auth-123"


def test_login_submit_failure_is_recorded_failed(env, monkeypatch):
    monkeypatch.setattr(
        login, "submit_code", lambda code: {"success": False, "output": "Invalid code"}
    )
    cmd = _enqueue(type="login_submit", payload={"code": "bad"})

    worker.drain("w")
    failed = _get(cmd["id"])
    assert failed["status"] == "failed"
    assert "Invalid code" in failed["error"]


def test_login_submit_without_code_is_failed(env):
    cmd = _enqueue(type="login_submit", payload={})
    assert worker.drain("w") == 1
    assert _get(cmd["id"])["status"] == "failed"


def test_bad_command_is_recorded_failed_not_raised(env):
    # spawn with no agent name -> CommandError -> the worker records 'failed', keeps going.
    _seed_project()
    cmd = _enqueue(type="spawn", project_id="p")
    assert worker.drain("w") == 1
    failed = _get(cmd["id"])
    assert failed["status"] == "failed"
    assert "agent name" in failed["error"]


def test_drain_processes_multiple_then_stops(env, monkeypatch):
    _seed_project()
    monkeypatch.setattr(poller, "sweep", lambda project_id=None: {"checked": 0})
    _enqueue(type="poll_ci", project_id="p")
    _enqueue(type="poll_ci", project_id="p")
    assert worker.drain("w") == 2
    assert worker.drain("w") == 0  # queue now empty
