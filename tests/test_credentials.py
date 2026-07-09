"""Credential resolution + env/helper derivation (README 3.7)."""

from __future__ import annotations

import pytest

from handler.control import credentials


def test_resolve_none_returns_none():
    assert credentials.resolve(None) is None
    assert credentials.resolve("") is None


def test_resolve_env(monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "secret-value")
    assert credentials.resolve("env:MY_TOKEN") == "secret-value"


def test_resolve_env_missing_raises(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    with pytest.raises(credentials.CredentialError, match="not set"):
        credentials.resolve("env:NOPE")


def test_resolve_file(tmp_path):
    f = tmp_path / "tok"
    f.write_text("  file-secret\n")
    assert credentials.resolve(f"file:{f}") == "file-secret"


def test_resolve_file_missing_raises(tmp_path):
    with pytest.raises(credentials.CredentialError, match="unreadable"):
        credentials.resolve(f"file:{tmp_path / 'absent'}")


def test_resolve_cmd():
    assert credentials.resolve("cmd:printf hunter2") == "hunter2"


def test_resolve_cmd_failure_raises():
    with pytest.raises(credentials.CredentialError, match="exited"):
        credentials.resolve("cmd:false")


def test_resolve_unknown_scheme_raises():
    with pytest.raises(credentials.CredentialError, match="unknown scheme"):
        credentials.resolve("vault:secret/x")


def test_resolve_empty_value_raises():
    with pytest.raises(credentials.CredentialError, match="no value"):
        credentials.resolve("env:")


def test_credential_env_always_sets_forge_token():
    env = credentials.credential_env("tok", None)
    assert env == {"FORGE_TOKEN": "tok"}


def test_credential_env_adds_host_specific_var():
    gh = credentials.credential_env("tok", "https://github.com/me/repo.git")
    assert gh["GITHUB_TOKEN"] == "tok" and gh["FORGE_TOKEN"] == "tok"
    gitea = credentials.credential_env("tok", "https://gitea.example.com/me/repo.git")
    assert gitea["GITEA_TOKEN"] == "tok"


def test_credential_env_empty_when_no_token():
    assert credentials.credential_env(None, "https://github.com/x") == {}


def test_git_credential_helper_reads_from_env():
    helper = credentials.git_credential_helper_value()
    # Inline helper hands back the token from $FORGE_TOKEN, never a value on disk.
    assert "$FORGE_TOKEN" in helper
    assert helper.startswith("!")


def test_remote_host_parses_https_and_ssh():
    assert credentials.remote_host("https://github.com/me/repo.git") == "github.com"
    assert credentials.remote_host("git@gitea.example.com:me/repo.git") == "gitea.example.com"
    assert credentials.remote_host(None) is None


def test_host_token_env_not_fooled_by_repo_name():
    # A GitHub repo merely *named* 'gitea' must not be mapped to GITEA_TOKEN.
    env = credentials.credential_env("tok", "https://github.com/me/gitea-mirror.git")
    assert "GITEA_TOKEN" not in env and env["GITHUB_TOKEN"] == "tok"


def test_host_token_env_self_hosted_hint():
    env = credentials.credential_env("tok", "https://gitea.mycorp.internal/me/repo.git")
    assert env["GITEA_TOKEN"] == "tok"


def test_git_credential_config_scoped_to_host():
    key, value = credentials.git_credential_config("https://github.com/me/repo.git")
    assert key == "credential.https://github.com.helper"
    assert "$FORGE_TOKEN" in value


def test_git_credential_config_none_for_ssh():
    assert credentials.git_credential_config("git@github.com:me/repo.git") is None
    assert credentials.git_credential_config(None) is None
