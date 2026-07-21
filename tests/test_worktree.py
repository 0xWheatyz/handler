"""Worktree resolution: the new-branch creation path, existing-branch checkout,
directory slugification, the isolation guard, and clear errors on git failure.

Uses real git repos in tmp_path — the whole point is git's actual behaviour (a bare
`worktree add <path> <branch>` only checks out an *existing* ref), which a mock can't
exercise.
"""

from __future__ import annotations

import subprocess

import pytest

from handler.control import worktree


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.co")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")  # hermetic: ignore any global signing
    _git(root, "commit", "-q", "--allow-empty", "-m", "init")
    return root


def _is_worktree(root, path) -> bool:
    out = subprocess.run(
        ["git", "-C", str(root), "worktree", "list", "--porcelain"],
        check=True, capture_output=True, text=True,
    ).stdout
    return str(path) in out


def test_creates_branch_when_it_does_not_exist(repo):
    # The regression: a fresh feature branch doesn't exist yet, so a bare `worktree add
    # <path> <branch>` used to fail with "invalid reference" (exit 128). It must create it.
    target = worktree.resolve_working_dir(
        str(repo), "feat-x", worktree_branch="feat/new-thing"
    )
    assert target.endswith("/feat-x")
    assert _is_worktree(repo, target)
    branches = subprocess.run(
        ["git", "-C", str(repo), "branch", "--list", "feat/new-thing"],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "feat/new-thing" in branches


def test_checks_out_existing_branch(repo):
    _git(repo, "branch", "feat/existing")
    target = worktree.resolve_working_dir(
        str(repo), "agent", worktree_branch="feat/existing"
    )
    assert _is_worktree(repo, target)
    head = subprocess.run(
        ["git", "-C", target, "rev-parse", "--abbrev-ref", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert head == "feat/existing"


def test_agent_name_is_slugified_for_the_directory(repo):
    # A free-form agent name (a PR title) must not put spaces/colons/parens in the path.
    name = "feat(claude-management): add claude skills management to webui"
    target = worktree.resolve_working_dir(
        str(repo), name, worktree_branch="feat/claude-management"
    )
    leaf = target.rsplit("/", 1)[-1]
    assert leaf == "feat-claude-management-add-claude-skills-management-to-webui"
    assert " " not in target and ":" not in leaf and "(" not in leaf


def test_worktree_error_carries_git_stderr(repo):
    # A path that already exists (an earlier worktree on the same slug) surfaces git's own
    # message, not a bare "exit status 128".
    worktree.resolve_working_dir(str(repo), "dup", worktree_branch="feat/one")
    with pytest.raises(worktree.WorktreeError) as exc:
        worktree.resolve_working_dir(str(repo), "dup", worktree_branch="feat/two")
    assert "already exists" in str(exc.value)


def test_rejects_worktree_and_subdir_together(repo):
    with pytest.raises(ValueError):
        worktree.resolve_working_dir(
            str(repo), "a", subdir="sub", worktree_branch="feat/x"
        )


def test_subdir_is_created_under_root(repo):
    target = worktree.resolve_working_dir(str(repo), "a", subdir="nested/dir")
    assert target.endswith("/nested/dir")
    import os
    assert os.path.isdir(target)


def test_subdir_escaping_root_is_rejected(repo):
    with pytest.raises(worktree.IsolationError):
        worktree.resolve_working_dir(str(repo), "a", subdir="../escape")


def test_no_subdir_no_branch_returns_root(repo):
    assert worktree.resolve_working_dir(str(repo), "a") == str(repo)
