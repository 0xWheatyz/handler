"""Git servers own their credentials: the encrypted token store, the per-server SSH
deploy key (public half visible, private half encrypted), and the resolution paths
that hand them to forge/git — including the now-live ``db:host:<hostname>`` scheme."""

from __future__ import annotations

import os
import stat

import pytest

from handler.control import credentials
from handler.db import repository as repo
from handler.db.engine import get_engine


@pytest.fixture
def secret_key(env, monkeypatch):
    from cryptography.fernet import Fernet

    from handler import config

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HANDLER_SECRET_KEY", key)
    config.get_settings.cache_clear()
    return key


# ------------------------------------------------------------------ secret store


def test_secretstore_roundtrip(secret_key):
    from handler import secretstore

    assert secretstore.enabled()
    assert secretstore.decrypt(secretstore.encrypt("s3cr3t")) == "s3cr3t"


def test_secretstore_refuses_without_key(env):
    from handler import secretstore

    assert not secretstore.enabled()
    with pytest.raises(secretstore.SecretStoreError, match="HANDLER_SECRET_KEY"):
        secretstore.encrypt("s3cr3t")


def test_secretstore_wrong_key_is_a_clear_error(secret_key, monkeypatch):
    from cryptography.fernet import Fernet

    from handler import config, secretstore

    ciphertext = secretstore.encrypt("s3cr3t")
    monkeypatch.setenv("HANDLER_SECRET_KEY", Fernet.generate_key().decode())
    config.get_settings.cache_clear()
    with pytest.raises(secretstore.SecretStoreError, match="HANDLER_SECRET_KEY changed"):
        secretstore.decrypt(ciphertext)


# ------------------------------------------------------------------ ssh keys


def test_generate_keypair_is_openssh_ed25519():
    from handler import sshkeys

    private, public = sshkeys.generate_keypair("handler@github.com")
    assert private.startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
    assert public.startswith("ssh-ed25519 ")
    assert public.endswith(" handler@github.com")


def test_materialize_private_key_is_0600_under_projects_root(env):
    from handler import sshkeys

    path = sshkeys.materialize_private_key("github.com", "KEYDATA")
    assert path.startswith(str(env["tmp"] / "projects"))
    assert os.path.basename(path) == "github.com"
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600
    with open(path) as fh:
        assert fh.read() == "KEYDATA\n"


def test_materialize_sanitizes_hostname(env):
    from handler import sshkeys

    path = sshkeys.materialize_private_key("../evil", "K")
    assert os.path.dirname(path).endswith(".ssh")
    assert "/../" not in path[len(str(env["tmp"])):]


# ------------------------------------------------------------------ hosts API


def test_create_host_with_token_and_ssh_key(client, auth, secret_key):
    r = client.post(
        "/hosts",
        json={
            "hostname": "github.com",
            "forge_type": "github",
            "token": "ghp_secret",
            "generate_ssh_key": True,
        },
        headers=auth,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_token"] is True
    assert body["ssh_public_key"].startswith("ssh-ed25519 ")
    # Secrets never leave the server, not even as keys in the payload.
    assert "token" not in body
    assert "token_enc" not in body
    assert "ssh_private_key_enc" not in body

    listed = client.get("/hosts", headers=auth).json()
    assert listed[0]["has_token"] is True
    assert "token_enc" not in listed[0]

    # The row itself holds ciphertext, not the token.
    with get_engine().begin() as conn:
        row = repo.get_host(conn, "github.com")
    assert row["token_enc"] != "ghp_secret"
    from handler import secretstore

    assert secretstore.decrypt(row["token_enc"]) == "ghp_secret"


def test_create_host_token_without_secret_key_is_400(client, auth):
    r = client.post(
        "/hosts",
        json={"hostname": "github.com", "forge_type": "github", "token": "x"},
        headers=auth,
    )
    assert r.status_code == 400
    assert "HANDLER_SECRET_KEY" in r.json()["detail"]


def test_patch_host_rotate_and_clear(client, auth, secret_key):
    r = client.post(
        "/hosts",
        json={
            "hostname": "gitea.corp",
            "forge_type": "gitea",
            "token": "old",
            "generate_ssh_key": True,
        },
        headers=auth,
    )
    first_key = r.json()["ssh_public_key"]

    r = client.patch(
        "/hosts/gitea.corp", json={"regenerate_ssh_key": True}, headers=auth
    )
    assert r.json()["ssh_public_key"] != first_key

    r = client.patch("/hosts/gitea.corp", json={"clear_token": True}, headers=auth)
    assert r.json()["has_token"] is False

    r = client.patch("/hosts/gitea.corp", json={"clear_ssh_key": True}, headers=auth)
    assert r.json()["ssh_public_key"] is None


# ------------------------------------------------------------------ resolution


def test_db_host_scheme_resolves_stored_token(secret_key):
    from handler import secretstore

    with get_engine().begin() as conn:
        repo.create_host(
            conn, "github.com", "github", token_enc=secretstore.encrypt("tok123")
        )
    assert credentials.resolve("db:host:github.com") == "tok123"


def test_db_host_scheme_missing_host_or_token(secret_key):
    with pytest.raises(credentials.CredentialError, match="not registered"):
        credentials.resolve("db:host:nowhere.example")
    with get_engine().begin() as conn:
        repo.create_host(conn, "bare.example", "gitea")
    with pytest.raises(credentials.CredentialError, match="no stored token"):
        credentials.resolve("db:host:bare.example")


def test_resolve_for_project_falls_back_to_server_token(secret_key):
    from handler import secretstore

    with get_engine().begin() as conn:
        repo.create_host(
            conn, "github.com", "github", token_enc=secretstore.encrypt("srv-tok")
        )
        project = {
            "id": "p",
            "git_remote": "git@github.com:me/repo.git",
            "credential_ref": None,
        }
        assert credentials.resolve_for_project(project, conn) == "srv-tok"
        # An explicit credential_ref still wins.
        os.environ["X_TOKEN"] = "own-tok"
        try:
            project["credential_ref"] = "env:X_TOKEN"
            assert credentials.resolve_for_project(project, conn) == "own-tok"
        finally:
            del os.environ["X_TOKEN"]


def test_resolve_for_project_none_without_anything(env):
    with get_engine().begin() as conn:
        project = {"id": "p", "git_remote": None, "credential_ref": None}
        assert credentials.resolve_for_project(project, conn) is None
