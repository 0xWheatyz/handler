"""Control-layer spawn: the hard test-task gate, settings generation, identity env."""

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


def test_spawn_refuses_without_test_task(env, fake_tmux):
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=False)
    _register_project(root)
    with pytest.raises(spawn.SpawnError, match="no \\[tasks.test\\]"):
        spawn.spawn("proj", "api")
    assert fake_tmux["calls"]["new_session"] == []


def test_spawn_refuses_without_mise_file(env, fake_tmux):
    root = env["tmp"] / "proj"
    root.mkdir(parents=True, exist_ok=True)
    _register_project(root)
    with pytest.raises(spawn.SpawnError, match="no .mise.toml"):
        spawn.spawn("proj", "api")


def test_spawn_creates_agent_settings_and_session(env, fake_tmux):
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)

    agent = spawn.spawn("proj", "api", task="build the thing")

    # Agent row created.
    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "proj", "api")["id"] == agent["id"]

    # settings.json wires all four hook events.
    settings = json.loads((root / ".claude" / "settings.json").read_text())
    assert set(settings["hooks"]) == {"Stop", "SessionEnd", "PreToolUse", "Notification"}
    pre = settings["hooks"]["PreToolUse"][0]
    assert pre["matcher"] == "AskUserQuestion|Bash"
    assert "handler.hooks pre_tool_use" in pre["hooks"][0]["command"]

    # tmux session named project__agent, with identity + DATABASE_URL in env.
    call = fake_tmux["calls"]["new_session"][0]
    assert call["name"] == "proj__api"
    assert call["env"]["HANDLER_PROJECT_ID"] == "proj"
    assert call["env"]["HANDLER_AGENT_NAME"] == "api"
    assert call["env"]["HANDLER_AGENT_ID"] == str(agent["id"])
    assert call["env"]["DATABASE_URL"] == env["url"]


def test_kill_sets_done_and_kills_session(env, fake_tmux):
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)
    spawn.spawn("proj", "api")

    spawn.kill("proj", "api")
    assert "proj__api" in fake_tmux["calls"]["kill_session"]
    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "proj", "api")["status"] == "done"


def test_resume_sends_answer_to_live_session(env, fake_tmux):
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)
    agent = spawn.spawn("proj", "api")

    ok, detail = spawn.resume(agent, "use Postgres")
    assert ok is True
    assert fake_tmux["calls"]["send_keys"][0] == {"name": "proj__api", "keys": "use Postgres"}
