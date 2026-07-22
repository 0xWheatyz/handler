"""Control-layer spawn: the hard test-task gate, settings generation, identity env.

Spawns go through the ``fake_launch`` seam (conftest) — the headless analogue of the old
fake tmux: it records the launch and mirrors its DB side effects, no subprocess."""

from __future__ import annotations

import json

import pytest

from handler.control import spawn
from handler.db import repository as repo
from handler.db.engine import get_engine


def _register_project(root):
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", str(root))


def _write_mise(root, with_test=True):
    root.mkdir(parents=True, exist_ok=True)
    body = "[tasks.lint]\nrun = 'ruff check .'\n"
    if with_test:
        body = "[tasks.test]\nrun = 'pytest'\n" + body
    (root / ".mise.toml").write_text(body)


def test_spawn_refuses_without_test_task(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=False)
    _register_project(root)
    with pytest.raises(spawn.SpawnError, match="no \\[tasks.test\\]"):
        spawn.spawn("proj", "api", task="do it")
    assert fake_launch == []


def test_spawn_refuses_without_mise_file(env, fake_launch):
    root = env["tmp"] / "proj"
    root.mkdir(parents=True, exist_ok=True)
    _register_project(root)
    with pytest.raises(spawn.SpawnError, match="no mise config"):
        spawn.spawn("proj", "api", task="do it")


def test_spawn_refuses_without_task(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register_project(root)
    with pytest.raises(spawn.SpawnError, match="requires a task"):
        spawn.spawn("proj", "api")
    # Fail-fast: no orphaned agent row behind the refused spawn.
    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "proj", "api") is None
    assert fake_launch == []


def test_spawn_accepts_dotless_mise_toml(env, fake_launch):
    # mise also reads `mise.toml` (no leading dot); the gate must honor it too.
    root = env["tmp"] / "proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / "mise.toml").write_text("[tasks.test]\nrun = 'pytest'\n")
    _register_project(root)

    agent = spawn.spawn("proj", "api", task="do it")
    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "proj", "api")["id"] == agent["id"]


def test_spawn_creates_agent_settings_and_run(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)

    agent = spawn.spawn("proj", "api", task="build the thing")

    # Agent row created.
    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "proj", "api")["id"] == agent["id"]

    # settings.json wires all four hook events AND the headless permission allowlist
    # (claude -p auto-denies anything that would prompt; the allowlist is what lets
    # normal work proceed — the hooks stay the hard gate).
    settings = json.loads((root / ".claude" / "settings.json").read_text())
    assert set(settings["hooks"]) == {"Stop", "SessionEnd", "PreToolUse", "Notification"}
    pre = settings["hooks"]["PreToolUse"][0]
    assert pre["matcher"] == "AskUserQuestion|Bash"
    assert "handler.hooks pre_tool_use" in pre["hooks"][0]["command"]
    assert settings["permissions"]["defaultMode"] == "acceptEdits"
    assert "Bash(git *)" in settings["permissions"]["allow"]

    # A headless run launched with identity + DATABASE_URL in env and the task as prompt.
    call = fake_launch[0]
    assert call["kind"] == "spawn"
    assert call["prompt"] == "build the thing"
    assert call["env"]["HANDLER_PROJECT_ID"] == "proj"
    assert call["env"]["HANDLER_AGENT_NAME"] == "api"
    assert call["env"]["HANDLER_AGENT_ID"] == str(agent["id"])
    assert call["env"]["DATABASE_URL"] == env["url"]
    # The run row + session id landed on the agent.
    with get_engine().begin() as conn:
        row = repo.get_agent_by_name(conn, "proj", "api")
        assert row["session_id"] == call["run"]["session_id"]
        assert repo.get_latest_run(conn, row["id"])["kind"] == "spawn"


def test_spawn_mise_init_skips_test_gate_and_marks_env(env, fake_launch):
    # A repo with no .mise.toml at all: the normal gate would refuse, but the mise-init
    # bootstrap agent must launch anyway (creating that file is its whole job).
    root = env["tmp"] / "proj"
    root.mkdir(parents=True, exist_ok=True)
    _register_project(root)

    agent = spawn.spawn(
        "proj", "mise-init", task="write the mise config", require_tests=False, mise_init=True
    )

    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "proj", "mise-init")["id"] == agent["id"]
    # The launched run carries HANDLER_MISE_INIT so its hooks enforce commit + push.
    assert fake_launch[0]["env"]["HANDLER_MISE_INIT"] == "1"


def test_spawn_still_gates_without_mise_init_flag(env, fake_launch):
    root = env["tmp"] / "proj"
    root.mkdir(parents=True, exist_ok=True)
    _register_project(root)
    # require_tests defaults on, so a normal spawn against a mise-less repo still refuses.
    with pytest.raises(spawn.SpawnError, match="no mise config"):
        spawn.spawn("proj", "api", task="do it")
    assert fake_launch == []


def test_kill_cancels_run_and_sets_done(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)
    spawn.spawn("proj", "api", task="do it")

    spawn.kill("proj", "api")
    with get_engine().begin() as conn:
        agent = repo.get_agent_by_name(conn, "proj", "api")
        assert agent["status"] == "done"
        # The running run was flagged; the owning supervisor terminates its own child.
        assert repo.get_latest_run(conn, agent["id"])["cancel_requested"] is True


def test_resume_reinjects_when_no_transcript(env, fake_launch):
    """A resume with no archive and no local transcript degrades to a fresh run whose
    prompt carries the operator's answer (context re-injection)."""
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)
    spawn.spawn("proj", "api", task="do it")
    with get_engine().begin() as conn:
        agent = repo.get_agent_by_name(conn, "proj", "api")
        repo.finish_run(conn, repo.get_latest_run(conn, agent["id"])["id"], "completed")

    ok, detail = spawn.resume(agent, "use Postgres")
    assert ok is True
    assert "re-injected" in detail
    assert fake_launch[-1]["kind"] == "spawn"
    assert "use Postgres" in fake_launch[-1]["prompt"]


def test_resume_refused_while_run_live(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)
    spawn.spawn("proj", "api", task="do it")  # fake run stays 'running'
    with get_engine().begin() as conn:
        agent = repo.get_agent_by_name(conn, "proj", "api")

    ok, detail = spawn.resume(agent, "answer")
    assert ok is False
    assert "live run" in detail
