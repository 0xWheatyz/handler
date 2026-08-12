"""The pi harness: config generation, the launch/resume paths against the fake ``pi``
binary, event normalization, and the API/spawn plumbing that selects it.

Same testing philosophy as the claude runner (``test_headless_run``): real
subprocesses, real threads, real SQLite — ``fake_pi.py`` stands in for the binary via
the ``pi_bin`` setting and emits genuine ``--mode json`` events, so what lands in the
DB is exactly what the API/UI will read. The bridge extension itself is TypeScript and
runs inside real pi, so here it is asserted as an artifact (installed, wired into
argv); its hook contract is the same ``python -m handler.hooks`` surface the hook tests
already cover.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from handler.control import headless, models, pi_harness, spawn
from handler.db import repository as repo
from handler.db.engine import get_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_PI = str(REPO_ROOT / "tests" / "fixtures" / "fake_pi.py")


@pytest.fixture
def pi_env(env, monkeypatch):
    from handler import config

    monkeypatch.setenv("PI_BIN", FAKE_PI)
    config.get_settings.cache_clear()
    yield env
    config.get_settings.cache_clear()


def _pi_row(**overrides):
    row = {
        "name": "qwen-local",
        "base_url": "http://127.0.0.1:8000/v1",
        "model": "qwen3-coder-30b",
        "small_fast_model": "qwen3-1.7b",
        "harness": "pi",
        "env": {},
    }
    row.update(overrides)
    return row


def _make_agent(tmp_path, name="p1", model_id=None):
    working_dir = tmp_path / "projects" / "p" / name
    working_dir.mkdir(parents=True)
    with get_engine().begin() as conn:
        if repo.get_project(conn, "p") is None:
            repo.create_project(conn, "p", str(tmp_path / "projects" / "p"))
        agent = repo.create_agent(conn, "p", name, str(working_dir), model_id=model_id)
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


# --- config generation -------------------------------------------------------------------


def test_write_config_renders_provider_and_bridge(pi_env, tmp_path):
    wd = str(tmp_path / "wd")
    base = pi_harness.write_config(wd, _pi_row(), "sk-local-123")

    provider = json.loads((base / "models.json").read_text())["providers"]["handler"]
    assert provider["baseUrl"] == "http://127.0.0.1:8000/v1"
    assert provider["api"] == "openai-completions"
    assert provider["apiKey"] == "sk-local-123"
    assert [m["id"] for m in provider["models"]] == ["qwen3-coder-30b", "qwen3-1.7b"]

    settings = json.loads((base / "settings.json").read_text())
    assert settings["defaultProvider"] == "handler"
    assert settings["defaultModel"] == "qwen3-coder-30b"
    # Skills parity: the web-managed sync's user dir plus the repo's committed skills.
    assert any(s.endswith(".claude/skills") for s in settings["skills"])
    assert any(s.startswith(wd) for s in settings["skills"])

    bridge = pi_harness.bridge_path(wd)
    assert bridge.exists()
    text = bridge.read_text()
    # The bridge is the hooks adapter — it must shell to the hook dispatcher and the
    # memory tool CLI, and register the question-deferral tool.
    assert "handler.hooks" in text
    assert "handler.mcpserver" in text
    assert "ask_operator" in text
    # Tool parity: the bridge activates pi's full built-in set (grep/find/ls are off
    # by default) alongside its own tools.
    assert "setActiveTools" in text
    assert (base / "APPEND_SYSTEM.md").read_text().strip()


def test_write_config_row_env_tunes_provider(pi_env, tmp_path):
    wd = str(tmp_path / "wd")
    row = _pi_row(
        env={
            "PI_PROVIDER_API": "anthropic-messages",
            "PI_CONTEXT_WINDOW": "32000",
            "PI_MAX_TOKENS": "4096",
            "SOME_VAR": "yes",
        }
    )
    base = pi_harness.write_config(wd, row, "k")
    provider = json.loads((base / "models.json").read_text())["providers"]["handler"]
    assert provider["api"] == "anthropic-messages"
    assert provider["models"][0]["contextWindow"] == 32000
    assert provider["models"][0]["maxTokens"] == 4096

    env = pi_harness.agent_env(wd, row)
    # Config-only keys are consumed by the writer, not leaked into the process env;
    # everything else passes through, and the defaults are present.
    assert "PI_PROVIDER_API" not in env
    assert env["SOME_VAR"] == "yes"
    assert env["PI_OFFLINE"] == "1"
    assert env["PI_CODING_AGENT_DIR"] == str(pi_harness.pi_dir(wd))
    assert env["HANDLER_PYTHON"]


def test_build_argv_wires_bridge_and_session(pi_env, tmp_path):
    wd = str(tmp_path / "wd")
    argv = pi_harness.build_argv("sid-1", wd)
    assert argv[1:5] == ["-p", "--mode", "json", "--no-extensions"]
    assert argv[argv.index("-e") + 1] == str(pi_harness.bridge_path(wd))
    assert argv[argv.index("--session") + 1] == str(pi_harness.session_file(wd, "sid-1"))
    # No prompt in argv: pi has no ``--`` separator, so the task travels on stdin.
    assert argv[-1] == str(pi_harness.session_file(wd, "sid-1"))


# --- model resolution --------------------------------------------------------------------


def test_resolve_model_and_harness(conn):
    row = repo.create_claude_model(
        conn, "qwen-pi", "http://127.0.0.1:8000/v1", "qwen3", harness="pi"
    )
    resolved = models.resolve_model(conn, row["id"])
    assert models.harness_of(resolved) == "pi"
    assert models.harness_of(None) == "claude"
    # A pi row produces no ANTHROPIC_* env — its config is files, not env.
    assert models.resolve_model_env(conn, row["id"]) == {}
    # claude rows are unchanged.
    claude_row = repo.create_claude_model(conn, "qwen-claude", "http://llm:4000", "qwen3")
    env = models.resolve_model_env(conn, claude_row["id"])
    assert env["ANTHROPIC_BASE_URL"] == "http://llm:4000"


# --- headless runs against the fake pi binary ---------------------------------------------


def test_pi_spawn_streams_events_and_completes(pi_env, tmp_path):
    agent = _make_agent(tmp_path)
    pi_harness.write_config(agent["working_dir"], _pi_row(), "k")
    run = headless.launch(
        agent, kind="spawn", prompt="build the thing",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="w1", harness="pi",
    )
    finished = _wait_for(_finished_run(run["id"]))
    assert finished is not None, "run never finished"
    assert finished["status"] == "completed"
    assert finished["exit_code"] == 0
    # agent_end normalized into the result the run row stores.
    assert finished["result"]["is_error"] is False
    assert finished["result"]["harness"] == "pi"

    with get_engine().begin() as conn:
        events = repo.list_agent_events(conn, agent["id"])
        updated = repo.get_agent_by_id(conn, agent["id"])
        archive = repo.get_session_archive(conn, agent["id"])

    types = [e["type"] for e in events]
    assert "session" in types and "agent_end" in types and "message_end" in types
    # last_output comes from assistant message_end events (user ones don't count).
    assert updated["last_output"] == "working on: build the thing"
    assert updated["status"] == "blocked"  # no hooks ran in the fake — not done
    assert updated["session_id"] == run["session_id"]
    # The single-file pi session was archived for cross-worker resume.
    assert archive is not None
    assert pi_harness.session_file(agent["working_dir"], run["session_id"]).exists()


def test_pi_failed_run_records_error_result(pi_env, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_PI_MODE", "error")
    agent = _make_agent(tmp_path, "p-err")
    run = headless.launch(
        agent, kind="spawn", prompt="boom",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="w1", harness="pi",
    )
    finished = _wait_for(_finished_run(run["id"]))
    assert finished["status"] == "failed"
    assert finished["exit_code"] == 1
    assert finished["result"]["is_error"] is True

    with get_engine().begin() as conn:
        events = repo.list_agent_events(conn, agent["id"])
        assert repo.get_agent_by_id(conn, agent["id"])["status"] == "blocked"
    raw = next(e for e in events if e["type"] == "raw")
    assert "this is not json" in raw["payload"]["line"]


def test_pi_cancel_terminates_hanging_run(pi_env, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_PI_MODE", "hang")
    agent = _make_agent(tmp_path, "p-hang")
    run = headless.launch(
        agent, kind="spawn", prompt="hang",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="w1", harness="pi",
    )
    _wait_for(lambda: _events_count(agent["id"]) >= 1)
    with get_engine().begin() as conn:
        assert repo.request_run_cancel(conn, run["id"]) is True
    finished = _wait_for(_finished_run(run["id"]), timeout=30.0)
    assert finished is not None and finished["status"] == "canceled"


def _events_count(agent_id):
    with get_engine().begin() as conn:
        return len(repo.list_agent_events(conn, agent_id))


def test_pi_cross_worker_resume_materializes_single_file(pi_env, tmp_path, monkeypatch):
    """Worker B resumes a pi session it never ran, from the DB archive alone — the pi
    analog of the claude linchpin test, on the single-file session layout."""
    with get_engine().begin() as conn:
        model = repo.create_claude_model(
            conn, "qwen-pi", "http://127.0.0.1:8000/v1", "qwen3", harness="pi"
        )
    agent = _make_agent(tmp_path, "p-resume", model_id=model["id"])
    pi_harness.write_config(agent["working_dir"], _pi_row(), "k")
    run = headless.launch(
        agent, kind="spawn", prompt="first pass",
        settings_path=str(tmp_path / "s.json"), env={}, worker_id="worker-a", harness="pi",
    )
    assert _wait_for(_finished_run(run["id"]))["status"] == "completed"

    # "Worker B": a clean HOME — no pi config, no session file.
    other_home = tmp_path / "worker-b-home"
    other_home.mkdir()
    monkeypatch.setenv("HOME", str(other_home))
    # The fake proves materialization: it exits 3 when the session file is absent.
    monkeypatch.setenv("FAKE_PI_EXPECT_HISTORY", "1")

    with get_engine().begin() as conn:
        agent = repo.get_agent_by_id(conn, agent["id"])
    ok, detail = spawn.resume(agent, "the operator's answer", worker_id="worker-b")
    assert ok, detail

    with get_engine().begin() as conn:
        resumed = repo.get_latest_run(conn, agent["id"])
    assert resumed["kind"] == "resume"
    finished = _wait_for(_finished_run(resumed["id"]))
    assert finished["status"] == "completed", f"exit={finished['exit_code']}"
    assert finished["session_id"] == run["session_id"]  # same session, continued
    # Resume regenerated the pi config under worker B's HOME (row edits reach resumes).
    assert pi_harness.pi_dir(agent["working_dir"]).exists()


# --- spawn plumbing ------------------------------------------------------------------------


def test_spawn_with_pi_model_launches_pi_harness(env, fake_launch, tmp_path):
    root = tmp_path / "projects" / "proj"
    root.mkdir(parents=True)
    (root / ".mise.toml").write_text("[tasks.test]\nrun = 'pytest'\n")
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", str(root))
        model = repo.create_claude_model(
            conn, "qwen-pi", "http://127.0.0.1:8000/v1", "qwen3", harness="pi"
        )

    agent = spawn.spawn("proj", "worker", task="do it", model_id=model["id"])
    call = fake_launch[0]
    assert call["harness"] == "pi"
    assert call["env"]["PI_CODING_AGENT_DIR"] == str(pi_harness.pi_dir(agent["working_dir"]))
    assert "ANTHROPIC_BASE_URL" not in call["env"]
    # The config artifacts were materialized before launch.
    assert pi_harness.bridge_path(agent["working_dir"]).exists()
    provider = json.loads(
        (pi_harness.pi_dir(agent["working_dir"]) / "models.json").read_text()
    )["providers"]["handler"]
    assert provider["baseUrl"] == "http://127.0.0.1:8000/v1"


def test_spawn_with_claude_model_still_launches_claude(env, fake_launch, tmp_path):
    root = tmp_path / "projects" / "proj2"
    root.mkdir(parents=True)
    (root / ".mise.toml").write_text("[tasks.test]\nrun = 'pytest'\n")
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj2", str(root))
        model = repo.create_claude_model(conn, "qwen-claude", "http://llm:4000", "qwen3")

    spawn.spawn("proj2", "worker", task="do it", model_id=model["id"])
    call = fake_launch[0]
    assert call["harness"] == "claude"
    assert call["env"]["ANTHROPIC_BASE_URL"] == "http://llm:4000"
    assert "PI_CODING_AGENT_DIR" not in call["env"]


# --- API -------------------------------------------------------------------------------------


def test_model_api_harness_round_trip(client, auth):
    r = client.post(
        "/claude/models",
        json={
            "name": "qwen-pi",
            "base_url": "http://127.0.0.1:8000/v1",
            "model": "qwen3",
            "harness": "pi",
        },
        headers=auth,
    )
    assert r.status_code == 201
    assert r.json()["harness"] == "pi"
    # Default stays claude, and junk is rejected with a clean 422.
    r = client.post(
        "/claude/models",
        json={"name": "plain", "base_url": "http://llm:4000", "model": "m"},
        headers=auth,
    )
    assert r.json()["harness"] == "claude"
    r = client.post(
        "/claude/models",
        json={"name": "bad", "base_url": "http://x", "model": "m", "harness": "aider"},
        headers=auth,
    )
    assert r.status_code == 422

    model_id = client.get("/claude/models", headers=auth).json()[0]["id"]
    r = client.patch(f"/claude/models/{model_id}", json={"harness": "pi"}, headers=auth)
    assert r.status_code == 200 and r.json()["harness"] == "pi"


# --- hook input: harness-provided final text --------------------------------------------------


def test_stop_checkpoint_prefers_harness_final_text(env, monkeypatch, tmp_path):
    """The pi bridge passes the closing message directly (pi session files aren't
    claude-transcript-shaped); the checkpoint must prefer it over the transcript parse."""
    from handler.hooks import checkpoint, verify
    from handler.hooks.context import HookInput, Identity

    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    agent = _make_agent(tmp_path, "hooked")
    ident = Identity(agent["id"], "p", "hooked", working_dir=agent["working_dir"])
    hook_input = HookInput(
        raw={"session_id": "s1", "final_assistant_text": "shipped the feature"},
        event="stop",
    )
    with get_engine().begin() as conn:
        result = checkpoint.handle_stop(conn, ident, hook_input)
        cm = repo.get_checkmark(conn, agent["id"])
    assert result == {}
    assert cm["status"] == "done"
    assert cm["where_it_stopped"] == "shipped the feature"
