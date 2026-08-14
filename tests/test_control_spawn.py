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

    # settings.json wires all five hook events AND the headless permission allowlist
    # (claude -p auto-denies anything that would prompt; the allowlist is what lets
    # normal work proceed — the hooks stay the hard gate).
    settings = json.loads((root / ".claude" / "settings.json").read_text())
    assert set(settings["hooks"]) == {
        "Stop",
        "SessionEnd",
        "SessionStart",
        "PreToolUse",
        "Notification",
    }
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


def test_spawn_trusts_working_dir_in_claude_json(env, fake_launch):
    """The launch must pre-trust the agent's working dir in ~/.claude.json — an
    untrusted workspace wedges a headless run on the trust dialog with nobody at a
    TTY (regression: the call was lost when phase 4 deleted the tmux launch path)."""
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)

    spawn.spawn("proj", "api", task="build the thing")

    cfg = json.loads((env["tmp"] / ".claude.json").read_text())
    assert cfg["hasCompletedOnboarding"] is True
    entry = cfg["projects"][str(root)]
    assert entry["hasTrustDialogAccepted"] is True


def test_resume_trusts_working_dir_in_claude_json(env, fake_launch):
    """Cross-worker resume may run in a container that has never seen this working
    dir; resume must re-seed trust exactly as spawn does."""
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)
    spawn.spawn("proj", "api", task="do it")
    with get_engine().begin() as conn:
        agent = repo.get_agent_by_name(conn, "proj", "api")
        repo.finish_run(conn, repo.get_latest_run(conn, agent["id"])["id"], "completed")
    (env["tmp"] / ".claude.json").unlink()  # a "fresh container": no config at all

    ok, _ = spawn.resume(agent, "use Postgres")

    assert ok is True
    cfg = json.loads((env["tmp"] / ".claude.json").read_text())
    assert cfg["projects"][str(root)]["hasTrustDialogAccepted"] is True


def _git(root, *args):
    import subprocess

    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        check=True,
        capture_output=True,
    )


def _init_git_repo(root):
    """A committed git repo with a test task — the shape of a real synced project."""
    _write_mise(root, with_test=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def test_spawn_defaults_to_isolated_worktree(env, fake_launch):
    """A no-placement spawn on a git root must NOT share the root checkout: the root
    only fast-forwards while parked on the default branch, so shared-root agents saw
    stale trees (missed pushes) as soon as one agent left it on a feature branch."""
    root = env["tmp"] / "proj"
    _init_git_repo(root)
    _register_project(root)

    agent = spawn.spawn("proj", "api", task="build the thing")

    assert agent["working_dir"] == str(root / "api")
    # A real worktree on the derived branch, not the root itself.
    assert (root / "api" / ".git").exists()
    import subprocess

    branch = subprocess.run(
        ["git", "-C", str(root / "api"), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branch == "agent/api"


def test_spawn_auto_worktree_off_keeps_root(env, fake_launch):
    root = env["tmp"] / "proj"
    _init_git_repo(root)
    _register_project(root)

    agent = spawn.spawn("proj", "api", task="do it", auto_worktree=False)

    assert agent["working_dir"] == str(root)


def test_spawn_non_git_root_still_uses_root(env, fake_launch):
    """Manual (non-git) projects keep the old placement — there is nothing to worktree."""
    root = env["tmp"] / "proj"
    _write_mise(root, with_test=True)
    _register_project(root)

    agent = spawn.spawn("proj", "api", task="do it")

    assert agent["working_dir"] == str(root)


def test_worker_spawn_scheduled_keeps_root_placement(env, monkeypatch):
    """Schedule firings opt out of the worktree default: their continuity convention
    is a state file living in the root tree across runs."""
    from handler.control import spawn as spawn_mod
    from handler.control import worker

    calls = []

    def fake_spawn(project_id, name, **kwargs):
        calls.append(kwargs)
        return {"id": 1, "name": name, "working_dir": "/x"}

    monkeypatch.setattr(spawn_mod, "spawn", fake_spawn)

    base = {"project_id": "proj", "agent_name": "a", "payload": {"task": "t"}}
    worker._cmd_spawn({**base, "requested_by": "schedule:5"})
    worker._cmd_spawn({**base, "requested_by": "operator:web"})

    assert calls[0]["auto_worktree"] is False
    assert calls[1]["auto_worktree"] is True
