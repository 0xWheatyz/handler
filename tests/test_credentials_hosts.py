"""Host-aware credential resolution: the forge_hosts registry overrides the built-in map
when a connection is supplied, and behaviour is unchanged when it isn't (regression)."""

from __future__ import annotations

from handler.control import credentials
from handler.db import repository as repo
from handler.db.engine import get_engine


def test_registry_host_overrides_builtin_env_var(env):
    with get_engine().begin() as conn:
        repo.create_host(conn, "github.com", "github", token_env_var="CORP_GH_TOKEN")
        e = credentials.credential_env("tok", "https://github.com/me/repo.git", conn)
    # Registry wins over the built-in GITHUB_TOKEN mapping.
    assert e["CORP_GH_TOKEN"] == "tok"
    assert e["FORGE_TOKEN"] == "tok"
    assert "GITHUB_TOKEN" not in e


def test_registry_enables_self_hosted_host(env):
    with get_engine().begin() as conn:
        repo.create_host(conn, "git.corp.internal", "gitea", token_env_var="CORP_TOKEN")
        e = credentials.credential_env("tok", "https://git.corp.internal/me/repo.git", conn)
    assert e["CORP_TOKEN"] == "tok"


def test_fallback_to_builtin_when_no_row(env):
    with get_engine().begin() as conn:
        e = credentials.credential_env("tok", "https://github.com/me/repo.git", conn)
    # No forge_hosts row -> built-in map still applies.
    assert e["GITHUB_TOKEN"] == "tok"


def test_no_conn_behaviour_is_unchanged():
    # The 2-arg form (no registry) must match the pre-existing built-in behaviour.
    e = credentials.credential_env("tok", "https://github.com/me/repo.git")
    assert e == {"FORGE_TOKEN": "tok", "GITHUB_TOKEN": "tok"}


def test_credential_config_uses_registry_base_url(env):
    with get_engine().begin() as conn:
        repo.create_host(conn, "git.corp", "gitea", base_url="https://git.corp:8443")
        key, value = credentials.git_credential_config("https://git.corp/me/repo.git", conn)
    assert key == "credential.https://git.corp:8443.helper"
    assert "$FORGE_TOKEN" in value


def test_db_scheme_is_reserved_not_yet_resolvable():
    import pytest

    with pytest.raises(credentials.CredentialError, match="reserved"):
        credentials.resolve("db:42")
