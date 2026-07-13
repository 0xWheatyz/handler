"""Shared fixtures. Everything runs on a fresh SQLite file per test, materialized via
a *real* ``alembic upgrade head`` — so the migration path itself is under test, not
just ``create_all``. No live claude/tmux/mise is ever touched: the three seams
(``control.tmux``, ``hooks.verify``, ``control.spawn.resume``) are faked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[1]


def _reset_caches() -> None:
    from handler import config
    from handler.db import engine

    config.get_settings.cache_clear()
    engine.get_engine.cache_clear()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point every entrypoint at a fresh SQLite db + a known token, migrated."""
    db_path = tmp_path / "handler.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("AUTH_TOKEN", "test-token")
    monkeypatch.setenv("SHARED_CONTEXT_WRITE_TOKEN", "shared-token")
    monkeypatch.setenv("PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    _reset_caches()

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "src" / "handler" / "migrations"))
    command.upgrade(cfg, "head")

    yield {"url": url, "token": "test-token", "shared_token": "shared-token", "tmp": tmp_path}

    _reset_caches()


@pytest.fixture
def engine(env):
    from handler.db.engine import get_engine

    return get_engine()


@pytest.fixture
def conn(engine):
    with engine.begin() as c:
        yield c


@pytest.fixture
def client(env):
    from fastapi.testclient import TestClient

    from handler.api.app import create_app

    return TestClient(create_app())


@pytest.fixture
def auth(env):
    return {"Authorization": f"Bearer {env['token']}"}


@pytest.fixture
def fake_tmux(monkeypatch):
    """Record tmux calls instead of spawning; report sessions as live by default."""
    calls: dict[str, list] = {"new_session": [], "kill_session": [], "send_keys": []}
    live: set[str] = set()

    from handler.control import tmux

    def new_session(name, cwd, command, env, *, width=None, height=None):
        calls["new_session"].append(
            {"name": name, "cwd": cwd, "command": command, "env": env,
             "width": width, "height": height}
        )
        live.add(name)

    def has_session(name):
        return name in live

    def kill_session(name):
        calls["kill_session"].append(name)
        live.discard(name)

    def send_keys(name, keys):
        calls["send_keys"].append({"name": name, "keys": keys})

    def list_sessions():
        return list(live)

    monkeypatch.setattr(tmux, "new_session", new_session)
    monkeypatch.setattr(tmux, "has_session", has_session)
    monkeypatch.setattr(tmux, "kill_session", kill_session)
    monkeypatch.setattr(tmux, "send_keys", send_keys)
    monkeypatch.setattr(tmux, "list_sessions", list_sessions)

    return {"calls": calls, "live": live}


@pytest.fixture
def fake_gitops(monkeypatch):
    """Fake the git seam: record config/add/commit, return a controllable branch/sha."""
    from handler.control import gitops

    state = {"branch": "feat/x", "sha": "abc123def456", "config": [], "add": [], "commit": []}

    def config_local(cwd, key, value):
        state["config"].append({"cwd": cwd, "key": key, "value": value})
        return True, ""

    def add(cwd, paths):
        state["add"].append({"cwd": cwd, "paths": paths})
        return True, ""

    def commit(cwd, message):
        state["commit"].append({"cwd": cwd, "message": message})
        return True, ""

    monkeypatch.setattr(gitops, "current_branch", lambda cwd: state["branch"])
    monkeypatch.setattr(gitops, "head_sha", lambda cwd: state["sha"])
    monkeypatch.setattr(gitops, "config_local", config_local)
    monkeypatch.setattr(gitops, "add", add)
    monkeypatch.setattr(gitops, "commit", commit)
    return state


@pytest.fixture
def fake_forge(monkeypatch):
    """Fake the forge seam: controllable version check + CI runs."""
    from handler.control import forge

    state = {"version_ok": True, "version_out": "forge 1.2.3", "ci_ok": True, "runs": []}

    monkeypatch.setattr(
        forge, "check_version", lambda cwd=".": (state["version_ok"], state["version_out"])
    )
    monkeypatch.setattr(forge, "ci_list", lambda cwd, sha: (state["ci_ok"], state["runs"]))
    monkeypatch.setattr(forge, "ci_log", lambda cwd, run_id: (True, "log"))
    return state
