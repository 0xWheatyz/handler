"""``sync_project`` against real git repos — the fetch-not-pull regression.

A pull only moves whichever branch the root has checked out; with the root parked on
an agent's feature branch, ``origin/*`` went stale and every branch cut for a new
agent started several commits behind the remote's default branch. These tests use a
filesystem remote (no host, no credentials) so the git behaviour itself is exercised.
"""

from __future__ import annotations

import subprocess

import pytest

from handler.control import reposync


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _sha(cwd, ref="HEAD") -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", ref],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def remote_and_root(tmp_path):
    """An origin repo, a clone of it as the project root, then origin moves ahead."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    for repo_dir in (origin,):
        _git(repo_dir, "config", "user.email", "t@t.co")
        _git(repo_dir, "config", "user.name", "t")
        _git(repo_dir, "config", "commit.gpgsign", "false")
    _git(origin, "commit", "-q", "--allow-empty", "-m", "one")
    root = tmp_path / "proj"
    subprocess.run(
        ["git", "clone", "-q", str(origin), str(root)], check=True, capture_output=True
    )
    _git(root, "config", "user.email", "t@t.co")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    _git(origin, "commit", "-q", "--allow-empty", "-m", "two")
    return origin, root


def _project(origin, root) -> dict:
    return {"id": "p", "root_dir": str(root), "git_remote": str(origin)}


def test_sync_refreshes_origin_even_when_root_parked_on_agent_branch(
    env, remote_and_root
):
    origin, root = remote_and_root
    _git(root, "checkout", "-q", "-b", "agent/old-work")
    # Simulate a clone that never had origin/HEAD — sync must re-pin it too.
    _git(root, "remote", "set-head", "origin", "-d")

    result = reposync.sync_project(_project(origin, root))

    assert result["action"] == "pulled"
    assert _sha(root, "origin/main") == _sha(origin, "main")
    assert _sha(root, "refs/remotes/origin/HEAD") == _sha(origin, "main")
    # The parked checkout itself is left alone — only origin/* moves.
    assert _sha(root, "HEAD") != _sha(origin, "main")


def test_sync_fast_forwards_a_checkout_sitting_on_the_default_branch(
    env, remote_and_root
):
    origin, root = remote_and_root
    result = reposync.sync_project(_project(origin, root))
    assert result["action"] == "pulled"
    assert _sha(root, "HEAD") == _sha(origin, "main")


def test_sync_fails_loudly_when_the_default_branch_diverged(env, remote_and_root):
    origin, root = remote_and_root
    _git(root, "commit", "-q", "--allow-empty", "-m", "local divergence")
    with pytest.raises(reposync.SyncError, match="fast-forward"):
        reposync.sync_project(_project(origin, root))
