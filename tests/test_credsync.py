"""Credential distribution through runtime_secrets: the login completes on one worker,
every other worker materializes the encrypted bundle from the DB — no shared files."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from handler.control import credsync
from handler.db import repository as repo
from handler.db.engine import get_engine


@pytest.fixture
def secret_env(env, monkeypatch):
    from handler import config

    monkeypatch.setenv("HANDLER_SECRET_KEY", Fernet.generate_key().decode())
    config.get_settings.cache_clear()
    credsync._state.__init__()  # fresh sync cursor per test
    yield env
    config.get_settings.cache_clear()


def _write_local_credentials(home: Path) -> None:
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"email": "op@example.com"}, "theme": "light"})
    )
    (home / ".claude" / ".credentials.json").write_text('{"token": "secret-oauth-token"}')


def test_upload_stores_encrypted_bundle(secret_env, tmp_path):
    _write_local_credentials(tmp_path)
    assert credsync.upload() is True
    with get_engine().begin() as conn:
        row = repo.get_runtime_secret(conn, credsync.SECRET_KEY)
    assert row is not None
    # Ciphertext at rest — the raw token must not appear in the DB value.
    assert "secret-oauth-token" not in row["value_enc"]


def test_refresh_materializes_on_fresh_worker(secret_env, tmp_path, monkeypatch):
    _write_local_credentials(tmp_path)
    assert credsync.upload() is True

    other_home = tmp_path / "worker-b"
    other_home.mkdir()
    monkeypatch.setenv("HOME", str(other_home))
    credsync._state.__init__()  # worker B's process state

    assert credsync.refresh() == "materialized"
    creds = json.loads((other_home / ".claude" / ".credentials.json").read_text())
    assert creds["token"] == "secret-oauth-token"
    data = json.loads((other_home / ".claude.json").read_text())
    assert data["oauthAccount"]["email"] == "op@example.com"
    # A second pass is a no-op — nothing changed anywhere.
    assert credsync.refresh() is None


def test_materialize_merges_claude_json_preserving_local_state(secret_env, tmp_path, monkeypatch):
    _write_local_credentials(tmp_path)
    credsync.upload()

    other_home = tmp_path / "worker-c"
    (other_home / ".claude").mkdir(parents=True)
    (other_home / ".claude.json").write_text(
        json.dumps(
            {
                "hasCompletedOnboarding": True,
                "theme": "dark",
                "projects": {"/projects/p/a": {"hasTrustDialogAccepted": True}},
            }
        )
    )
    monkeypatch.setenv("HOME", str(other_home))
    credsync._state.__init__()

    assert credsync.refresh() == "materialized"
    data = json.loads((other_home / ".claude.json").read_text())
    # Account arrived...
    assert data["oauthAccount"]["email"] == "op@example.com"
    # ...but this worker's own onboarding/trust state (claude_config's writes) survived.
    assert data["theme"] == "dark"
    assert data["projects"]["/projects/p/a"]["hasTrustDialogAccepted"] is True


def test_refresh_uploads_local_change(secret_env, tmp_path):
    _write_local_credentials(tmp_path)
    assert credsync.refresh() == "uploaded"  # bootstrap: local creds, empty DB
    # A token refresh on disk (mtime/size change) re-publishes.
    os.utime(tmp_path / ".claude" / ".credentials.json", ns=(1, 1))
    assert credsync.refresh() == "uploaded"


def test_disabled_without_secret_key(env, tmp_path):
    _write_local_credentials(tmp_path)
    assert credsync.upload() is False
    assert credsync.refresh() is None
