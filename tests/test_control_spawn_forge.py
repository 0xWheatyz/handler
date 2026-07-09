"""Phase 2 spawn wiring: credential injection, git helper, forge version note, role."""

from __future__ import annotations

import pytest

from handler.control import spawn
from handler.db import repository as repo
from handler.db.engine import get_engine


def _write_mise(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / ".mise.toml").write_text("[tasks.test]\nrun = 'pytest'\n")


def _register(root, **kw):
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", str(root), **kw)


def test_spawn_injects_credentials_and_installs_helper(env, fake_tmux, fake_gitops, monkeypatch):
    monkeypatch.setenv("PROJ_TOKEN", "s3cret")
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register(root, git_remote="https://github.com/me/proj.git", credential_ref="env:PROJ_TOKEN")

    spawn.spawn("proj", "junior", role="junior")

    call = fake_tmux["calls"]["new_session"][0]
    # Token injected under the generic + host-specific names, never the raw ref stored.
    assert call["env"]["FORGE_TOKEN"] == "s3cret"
    assert call["env"]["GITHUB_TOKEN"] == "s3cret"
    assert call["env"]["HANDLER_AGENT_ROLE"] == "junior"
    # Git credential helper installed, scoped to the forge host (not global).
    helper = [c for c in fake_gitops["config"] if c["key"].endswith(".helper")]
    assert helper and helper[0]["key"] == "credential.https://github.com.helper"
    assert "$FORGE_TOKEN" in helper[0]["value"]


def test_spawn_ssh_remote_installs_no_https_helper(env, fake_tmux, fake_gitops, monkeypatch):
    monkeypatch.setenv("PROJ_TOKEN", "s3cret")
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register(root, git_remote="git@github.com:me/proj.git", credential_ref="env:PROJ_TOKEN")
    spawn.spawn("proj", "junior", role="junior")
    # ssh remote -> token still injected, but no HTTPS credential helper installed.
    assert fake_tmux["calls"]["new_session"][0]["env"]["GITHUB_TOKEN"] == "s3cret"
    assert fake_gitops["config"] == []


def test_spawn_fails_fast_on_broken_credential_ref(env, fake_tmux, fake_gitops, monkeypatch):
    monkeypatch.delenv("ABSENT_TOKEN", raising=False)
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register(root, credential_ref="env:ABSENT_TOKEN")

    with pytest.raises(spawn.SpawnError, match="not set"):
        spawn.spawn("proj", "junior", role="junior")
    # No agent row and no session left behind by the failed spawn.
    with get_engine().begin() as conn:
        assert repo.get_agent_by_name(conn, "proj", "junior") is None
    assert fake_tmux["calls"]["new_session"] == []


def test_spawn_without_credential_ref_injects_no_token(env, fake_tmux, fake_gitops):
    root = env["tmp"] / "proj"
    _write_mise(root)
    _register(root)
    spawn.spawn("proj", "api")
    call = fake_tmux["calls"]["new_session"][0]
    assert "FORGE_TOKEN" not in call["env"]
    # No token -> no credential helper installed.
    assert fake_gitops["config"] == []


def test_spawn_reports_forge_version_mismatch(env, fake_tmux, fake_gitops, fake_forge, monkeypatch):
    monkeypatch.setenv("FORGE_VERSION", "9.9.9")
    from handler import config
    from handler.db import engine

    config.get_settings.cache_clear()
    engine.get_engine.cache_clear()

    root = env["tmp"] / "proj"
    _write_mise(root)
    _register(root)
    fake_forge["version_ok"] = False
    fake_forge["version_out"] = "forge 1.2.3"

    agent = spawn.spawn("proj", "api")
    assert "9.9.9" in agent["forge_note"]
