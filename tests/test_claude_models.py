"""Model backends: /claude/models CRUD + admin gating, the env the control layer builds
from a selected backend, and the spawn/resume/worker integration that pins an agent to it.

A backend never changes *how* an agent launches — same ``claude -p``, same settings/
hooks — only the ``ANTHROPIC_*`` environment, so the tests assert on the env the
``fake_launch`` seam records.
"""

from __future__ import annotations

import pytest

from handler.control import cli, models, spawn, worker
from handler.db import repository as repo
from handler.db.engine import connection, get_engine


@pytest.fixture
def lowpriv(env):
    """A valid bearer that is NOT the admin token (the shared-context write token)."""
    return {"Authorization": f"Bearer {env['shared_token']}"}


@pytest.fixture
def secret_key(env, monkeypatch):
    from cryptography.fernet import Fernet

    from handler import config

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HANDLER_SECRET_KEY", key)
    config.get_settings.cache_clear()
    return key


def _register_project(root):
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", str(root))


def _write_mise(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / ".mise.toml").write_text("[tasks.test]\nrun = 'pytest'\n")


# --- repository ------------------------------------------------------------------------


def test_repository_model_crud(conn):
    row = repo.create_claude_model(
        conn, "qwen3-coder", "http://llm.local:4000", "qwen3-coder-30b"
    )
    assert row["enabled"] is True and row["api_key_enc"] is None
    assert repo.get_claude_model_by_name(conn, "qwen3-coder")["id"] == row["id"]

    updated = repo.update_claude_model(
        conn, row["id"], small_fast_model="qwen3-1.7b", enabled=False
    )
    assert updated["small_fast_model"] == "qwen3-1.7b" and updated["enabled"] is False
    assert repo.list_claude_models(conn, enabled_only=True) == []
    assert len(repo.list_claude_models(conn)) == 1

    assert repo.delete_claude_model(conn, row["id"]) is True
    assert repo.get_claude_model(conn, row["id"]) is None


# --- API CRUD + gating -----------------------------------------------------------------


def test_model_api_crud_never_returns_key(client, auth, secret_key):
    r = client.post(
        "/claude/models",
        json={
            "name": "qwen3-coder",
            "base_url": "http://llm.local:4000/",  # trailing slash normalized away
            "model": "qwen3-coder-30b",
            "api_key": "sk-local-123",
            "env": {"API_TIMEOUT_MS": "600000"},
        },
        headers=auth,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["base_url"] == "http://llm.local:4000"
    assert body["has_api_key"] is True
    assert "sk-local-123" not in r.text and "api_key_enc" not in body
    mid = body["id"]

    # The stored column is ciphertext, not the key.
    with get_engine().begin() as conn:
        stored = repo.get_claude_model(conn, mid)["api_key_enc"]
    assert stored and "sk-local-123" not in stored

    # Duplicate name refused.
    r = client.post(
        "/claude/models",
        json={"name": "qwen3-coder", "base_url": "http://x", "model": "m"},
        headers=auth,
    )
    assert r.status_code == 409

    # PATCH: clear the key; other fields survive.
    r = client.patch(
        f"/claude/models/{mid}", json={"clear_api_key": True, "enabled": False}, headers=auth
    )
    assert r.status_code == 200
    assert r.json()["has_api_key"] is False and r.json()["enabled"] is False

    r = client.delete(f"/claude/models/{mid}", headers=auth)
    assert r.status_code == 200 and r.json()["deleted"] == "qwen3-coder"


def test_model_api_validation_and_admin_gating(client, auth, lowpriv):
    # base_url must be http(s).
    r = client.post(
        "/claude/models",
        json={"name": "bad", "base_url": "llm.local:4000", "model": "m"},
        headers=auth,
    )
    assert r.status_code == 422

    r = client.post(
        "/claude/models",
        json={"name": "ok", "base_url": "http://llm.local", "model": "m"},
        headers=auth,
    )
    assert r.status_code == 201
    mid = r.json()["id"]

    # Reads take the normal token; writes need admin.
    assert client.get("/claude/models", headers=lowpriv).status_code == 200
    assert (
        client.post(
            "/claude/models",
            json={"name": "x", "base_url": "http://y", "model": "m"},
            headers=lowpriv,
        ).status_code
        == 403
    )
    assert client.patch(f"/claude/models/{mid}", json={}, headers=lowpriv).status_code == 403
    assert client.delete(f"/claude/models/{mid}", headers=lowpriv).status_code == 403


def test_model_api_key_without_secret_store_is_400(client, auth):
    r = client.post(
        "/claude/models",
        json={"name": "k", "base_url": "http://x", "model": "m", "api_key": "sk-1"},
        headers=auth,
    )
    assert r.status_code == 400
    assert "HANDLER_SECRET_KEY" in r.json()["detail"]


# --- env resolution --------------------------------------------------------------------


def test_resolve_model_env_none_is_subscription(conn):
    assert models.resolve_model_env(conn, None) == {}


def test_resolve_model_env_defaults_and_overrides(conn):
    row = repo.create_claude_model(
        conn,
        "qwen3-coder",
        "http://llm.local:4000",
        "qwen3-coder-30b",
        env={"CLAUDE_CODE_MAX_OUTPUT_TOKENS": "8192"},
    )
    env = models.resolve_model_env(conn, row["id"])
    assert env["ANTHROPIC_BASE_URL"] == "http://llm.local:4000"
    assert env["ANTHROPIC_MODEL"] == "qwen3-coder-30b"
    # No small_fast_model configured -> the main model serves the fast lane too.
    assert env["ANTHROPIC_SMALL_FAST_MODEL"] == "qwen3-coder-30b"
    # No stored key -> placeholder, so the subscription OAuth token never leaves for a
    # local endpoint.
    assert env["ANTHROPIC_AUTH_TOKEN"] == "handler-local"
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "8192"


def test_resolve_model_env_decrypts_key(conn, secret_key):
    from handler import secretstore

    row = repo.create_claude_model(
        conn,
        "gateway",
        "https://gw.corp",
        "big-model",
        api_key_enc=secretstore.encrypt("sk-real"),
        small_fast_model="small-model",
    )
    env = models.resolve_model_env(conn, row["id"])
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-real"
    assert env["ANTHROPIC_SMALL_FAST_MODEL"] == "small-model"


def test_resolve_model_env_missing_and_disabled(conn):
    with pytest.raises(models.ModelError, match="no longer exists"):
        models.resolve_model_env(conn, 999)
    row = repo.create_claude_model(conn, "off", "http://x", "m", enabled=False)
    with pytest.raises(models.ModelError, match="disabled"):
        models.resolve_model_env(conn, row["id"], require_enabled=True)
    # A resume (require_enabled=False) may still use a disabled backend.
    assert models.resolve_model_env(conn, row["id"])["ANTHROPIC_MODEL"] == "m"


# --- spawn / resume / worker integration -----------------------------------------------


def test_spawn_with_model_injects_env_and_pins_agent(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register_project(root)
    with get_engine().begin() as conn:
        row = repo.create_claude_model(conn, "qwen3-coder", "http://llm.local:4000", "qwen")

    agent = spawn.spawn("proj", "api", task="do it", model_id=row["id"])

    call_env = fake_launch[0]["env"]
    assert call_env["ANTHROPIC_BASE_URL"] == "http://llm.local:4000"
    assert call_env["ANTHROPIC_MODEL"] == "qwen"
    # Identity/credential env still rides along untouched.
    assert call_env["HANDLER_PROJECT_ID"] == "proj"
    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "proj", "api")["model_id"] == row["id"]
    assert agent["model_id"] == row["id"]


def test_spawn_without_model_keeps_subscription_env(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register_project(root)
    spawn.spawn("proj", "api", task="do it")
    assert "ANTHROPIC_BASE_URL" not in fake_launch[0]["env"]
    assert "ANTHROPIC_AUTH_TOKEN" not in fake_launch[0]["env"]


def test_spawn_refuses_missing_or_disabled_model(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register_project(root)
    with pytest.raises(spawn.SpawnError, match="no longer exists"):
        spawn.spawn("proj", "api", task="do it", model_id=12345)
    with get_engine().begin() as conn:
        off = repo.create_claude_model(conn, "off", "http://x", "m", enabled=False)
        # Fail-fast: no orphaned agent row behind the refused spawn.
        assert repo.get_agent_by_name(conn, "proj", "api") is None
    with pytest.raises(spawn.SpawnError, match="disabled"):
        spawn.spawn("proj", "api", task="do it", model_id=off["id"])
    assert fake_launch == []


def test_resume_comes_back_on_the_same_backend(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register_project(root)
    with get_engine().begin() as conn:
        row = repo.create_claude_model(conn, "qwen3-coder", "http://llm.local:4000", "qwen")
    spawn.spawn("proj", "api", task="do it", model_id=row["id"])
    with get_engine().begin() as conn:
        agent = repo.get_agent_by_name(conn, "proj", "api")
        repo.finish_run(conn, repo.get_latest_run(conn, agent["id"])["id"], "completed")

    ok, _ = spawn.resume(agent, "keep going")
    assert ok is True
    assert fake_launch[-1]["env"]["ANTHROPIC_BASE_URL"] == "http://llm.local:4000"


def test_resume_fails_loudly_when_backend_deleted(env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register_project(root)
    with get_engine().begin() as conn:
        row = repo.create_claude_model(conn, "qwen3-coder", "http://llm.local:4000", "qwen")
    spawn.spawn("proj", "api", task="do it", model_id=row["id"])
    with get_engine().begin() as conn:
        agent = repo.get_agent_by_name(conn, "proj", "api")
        repo.finish_run(conn, repo.get_latest_run(conn, agent["id"])["id"], "completed")
        repo.delete_claude_model(conn, row["id"])

    with pytest.raises(spawn.SpawnError, match="no longer exists"):
        spawn.resume(agent, "keep going")


def test_spawn_route_and_worker_pass_model_through(client, auth, env, fake_launch):
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register_project(root)
    with get_engine().begin() as conn:
        row = repo.create_claude_model(conn, "qwen3-coder", "http://llm.local:4000", "qwen")
        off = repo.create_claude_model(conn, "off", "http://x", "m", enabled=False)

    # Fail-fast at enqueue time for a stale/disabled dropdown selection.
    r = client.post(
        "/projects/proj/agents/spawn",
        json={"name": "a", "task": "t", "model_id": 999},
        headers=auth,
    )
    assert r.status_code == 400 and "not found" in r.json()["detail"]
    r = client.post(
        "/projects/proj/agents/spawn",
        json={"name": "a", "task": "t", "model_id": off["id"]},
        headers=auth,
    )
    assert r.status_code == 400 and "disabled" in r.json()["detail"]

    r = client.post(
        "/projects/proj/agents/spawn",
        json={"name": "api", "task": "do it", "model_id": row["id"]},
        headers=auth,
    )
    assert r.status_code == 202
    assert r.json()["payload"]["model_id"] == row["id"]

    with connection() as conn:
        command = repo.claim_next_command(conn, "w1")
    result = worker.execute_command(command)
    assert result["name"] == "api"
    assert fake_launch[0]["env"]["ANTHROPIC_MODEL"] == "qwen"

    # The agent row the API returns carries the pin, so the UI can badge it.
    r = client.get("/projects/proj/agents", headers=auth)
    assert r.json()[0]["model_id"] == row["id"]


def test_cli_spawn_resolves_model_by_name(env, fake_launch, capsys):
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register_project(root)

    assert cli.main(["spawn", "--project", "proj", "--name", "a", "--task", "t",
                     "--model", "nope"]) == 1
    assert "not registered" in capsys.readouterr().err

    with get_engine().begin() as conn:
        repo.create_claude_model(conn, "qwen3-coder", "http://llm.local:4000", "qwen")
    assert cli.main(["spawn", "--project", "proj", "--name", "api", "--task", "t",
                     "--model", "qwen3-coder"]) == 0
    assert fake_launch[0]["env"]["ANTHROPIC_BASE_URL"] == "http://llm.local:4000"
