"""Project registration in git-server mode: pick a registered server, type owner/name,
and Handler derives the remote + root_dir and enqueues the clone. The worker's ``sync``
command (and the reposync module under it) is exercised against the gitops mock seam."""

from __future__ import annotations

import os

import pytest

from handler.control import gitops, reposync, worker
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


def _add_server(client, auth, hostname="github.com", **extra):
    body = {"hostname": hostname, "forge_type": "github", **extra}
    r = client.post("/hosts", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_project_from_server_with_ssh_key(client, auth, env, secret_key):
    _add_server(client, auth, generate_ssh_key=True)
    r = client.post(
        "/projects", json={"git_server": "github.com", "repo": "me/CoolProj"}, headers=auth
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # id derived from the repo name; root under PROJECTS_ROOT; ssh remote (a key exists).
    assert body["id"] == "coolproj"
    assert body["root_dir"] == os.path.join(str(env["tmp"] / "projects"), "coolproj")
    assert body["git_remote"] == "git@github.com:me/CoolProj.git"
    # The clone is enqueued for the worker.
    assert body["sync_command_id"] is not None
    cmd = client.get(f"/commands/{body['sync_command_id']}", headers=auth).json()
    assert cmd["type"] == "sync"
    assert cmd["project_id"] == "coolproj"


def test_create_project_with_init_mise_enqueues_bootstrap(client, auth, env, secret_key):
    _add_server(client, auth, generate_ssh_key=True)
    r = client.post(
        "/projects",
        json={"git_server": "github.com", "repo": "me/coolproj", "init_mise": True},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sync_command_id"] is not None
    assert body["mise_init_command_id"] is not None
    # The clone is queued before the bootstrap so it runs first (FIFO by id).
    assert body["mise_init_command_id"] > body["sync_command_id"]
    cmd = client.get(f"/commands/{body['mise_init_command_id']}", headers=auth).json()
    assert cmd["type"] == "mise_init"
    assert cmd["project_id"] == "coolproj"


def test_create_project_without_init_mise_skips_bootstrap(client, auth, env, secret_key):
    _add_server(client, auth, generate_ssh_key=True)
    r = client.post(
        "/projects", json={"git_server": "github.com", "repo": "me/plain"}, headers=auth
    )
    assert r.status_code == 201, r.text
    assert r.json()["mise_init_command_id"] is None


def test_init_mise_without_remote_does_not_enqueue(client, auth, env, tmp_path):
    # Manual mode with no git_remote: nothing to push to, so no bootstrap is queued.
    root = tmp_path / "local"
    root.mkdir()
    r = client.post(
        "/projects",
        json={"id": "local", "root_dir": str(root), "init_mise": True},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    assert r.json()["mise_init_command_id"] is None


def test_create_project_from_server_https_without_key(client, auth, env):
    _add_server(client, auth, hostname="git.corp", forge_type="gitea",
                base_url="https://git.corp:8443")
    r = client.post(
        "/projects", json={"git_server": "git.corp", "repo": "me/repo", "id": "corp-repo"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    assert r.json()["git_remote"] == "https://git.corp:8443/me/repo.git"
    assert r.json()["id"] == "corp-repo"


def test_create_project_unknown_server_404(client, auth, env):
    r = client.post(
        "/projects", json={"git_server": "nowhere.example", "repo": "a/b"}, headers=auth
    )
    assert r.status_code == 404


def test_create_project_bad_repo_422(client, auth, env):
    r = client.post(
        "/projects", json={"git_server": "github.com", "repo": "not-owner-name"}, headers=auth
    )
    assert r.status_code == 422


def test_manual_mode_still_requires_id_and_root(client, auth, env):
    r = client.post("/projects", json={"root_dir": "/tmp/x"}, headers=auth)
    assert r.status_code == 422
    r = client.post("/projects", json={"id": "x"}, headers=auth)
    assert r.status_code == 422


def test_sync_endpoint_enqueues(client, auth, env, tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    client.post(
        "/projects",
        json={"id": "p1", "root_dir": str(root), "git_remote": "https://github.com/a/b.git"},
        headers=auth,
    )
    r = client.post("/projects/p1/sync", headers=auth)
    assert r.status_code == 202
    assert r.json()["type"] == "sync"


def test_sync_endpoint_400_without_remote(client, auth, env, tmp_path):
    root = tmp_path / "proj2"
    root.mkdir()
    client.post("/projects", json={"id": "p2", "root_dir": str(root)}, headers=auth)
    r = client.post("/projects/p2/sync", headers=auth)
    assert r.status_code == 400


# ------------------------------------------------------------------ worker sync command


@pytest.fixture
def fake_sync_gitops(monkeypatch):
    """Fake the clone/pull side of the gitops seam."""
    state = {"clone": [], "fetch": [], "config": [], "repos": set(), "ok": True, "out": ""}

    def is_repo(path):
        return path in state["repos"]

    def clone(remote, dest, env=None, config=None):
        state["clone"].append({"remote": remote, "dest": dest, "env": env or {},
                               "config": config or []})
        if state["ok"]:
            state["repos"].add(dest)
        return state["ok"], state["out"]

    def fetch(cwd, env=None):
        state["fetch"].append({"cwd": cwd, "env": env or {}})
        return state["ok"], state["out"]

    def set_default_head(cwd, env=None):
        return True, ""

    def default_branch_ref(cwd):
        return None

    def config_local(cwd, key, value):
        state["config"].append({"cwd": cwd, "key": key, "value": value})
        return True, ""

    monkeypatch.setattr(gitops, "is_repo", is_repo)
    monkeypatch.setattr(gitops, "clone", clone)
    monkeypatch.setattr(gitops, "fetch", fetch)
    monkeypatch.setattr(gitops, "set_default_head", set_default_head)
    monkeypatch.setattr(gitops, "default_branch_ref", default_branch_ref)
    monkeypatch.setattr(gitops, "config_local", config_local)
    return state


def _register(conn, project_id="p", remote="https://github.com/me/repo.git", root="/tmp/r"):
    return repo.create_project(conn, project_id, root_dir=root, git_remote=remote)


def test_cmd_sync_clones_then_pulls(env, fake_sync_gitops):
    with get_engine().begin() as conn:
        _register(conn)
        command = repo.enqueue_command(conn, "sync", project_id="p")

    result = worker.execute_command(command)
    assert result["action"] == "cloned"
    assert fake_sync_gitops["clone"][0]["remote"] == "https://github.com/me/repo.git"

    result = worker.execute_command(command)
    assert result["action"] == "pulled"
    assert fake_sync_gitops["fetch"][0]["cwd"] == "/tmp/r"


def test_cmd_sync_failure_is_command_error(env, fake_sync_gitops):
    fake_sync_gitops["ok"] = False
    fake_sync_gitops["out"] = "fatal: repository not found"
    with get_engine().begin() as conn:
        _register(conn)
        command = repo.enqueue_command(conn, "sync", project_id="p")
    with pytest.raises(worker.CommandError, match="repository not found"):
        worker.execute_command(command)


def test_sync_uses_server_token_and_installs_helper(env, secret_key, fake_sync_gitops):
    from handler import secretstore

    with get_engine().begin() as conn:
        repo.create_host(conn, "github.com", "github",
                         token_enc=secretstore.encrypt("srv-tok"))
        project = _register(conn)

    result = reposync.sync_project(project)
    assert result["action"] == "cloned"
    call = fake_sync_gitops["clone"][0]
    # Token flows through the env (never argv/disk), helper is scoped to the host and
    # persisted into the fresh clone for the agents that follow.
    assert call["env"]["FORGE_TOKEN"] == "srv-tok"
    assert call["env"]["GITHUB_TOKEN"] == "srv-tok"
    assert any(k.startswith("credential.https://github.com") for k, _ in call["config"])
    assert any(c["key"].startswith("credential.") for c in fake_sync_gitops["config"])


def test_sync_ssh_remote_uses_deploy_key(env, secret_key, fake_sync_gitops):
    from handler import secretstore, sshkeys

    private, public = sshkeys.generate_keypair("handler@github.com")
    with get_engine().begin() as conn:
        repo.create_host(conn, "github.com", "github", ssh_public_key=public,
                         ssh_private_key_enc=secretstore.encrypt(private))
        project = _register(conn, remote="git@github.com:me/repo.git")

    result = reposync.sync_project(project)
    assert result["action"] == "cloned"
    env_used = fake_sync_gitops["clone"][0]["env"]
    assert "GIT_SSH_COMMAND" in env_used
    assert "IdentitiesOnly=yes" in env_used["GIT_SSH_COMMAND"]
    # The pinned key is persisted for the agents (core.sshCommand).
    assert any(c["key"] == "core.sshCommand" for c in fake_sync_gitops["config"])
    # And the key file was materialized 0600.
    key_path = env_used["GIT_SSH_COMMAND"].split(" -i ", 1)[1].split(" ")[0]
    with open(key_path) as fh:
        assert "OPENSSH PRIVATE KEY" in fh.read()
