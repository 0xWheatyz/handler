"""Per-agent working directory setup — a subdirectory under the project root, or a
git worktree. The isolation invariant: the resulting path is always under the project
root (README 3.4), never reaching into another project's tree.
"""

from __future__ import annotations

import os
import re
import subprocess


class IsolationError(Exception):
    """Raised when a requested working dir would escape the project root."""


class WorktreeError(Exception):
    """Raised when ``git worktree add`` fails, carrying git's own stderr."""


def _under(root: str, path: str) -> bool:
    root_abs = os.path.realpath(root)
    path_abs = os.path.realpath(path)
    return path_abs == root_abs or path_abs.startswith(root_abs + os.sep)


def _slug(name: str) -> str:
    """A filesystem-safe directory name derived from an agent name.

    Agent names can be free-form (a PR title, a branch expression) and land here as a
    directory under the project root, so collapse anything that isn't ``[A-Za-z0-9._-]``
    to a single dash. Keeps the repo root free of paths with spaces, colons, and parens.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    return slug or "agent"


def _default_branch_start(project_root: str) -> str | None:
    """The remote default branch ref (``origin/main``) when the clone knows it.

    New agent branches are cut from here rather than the root's ``HEAD``: the root
    checkout can legitimately be parked on some earlier agent's branch, and cutting
    from it handed fresh agents history that was hours behind the remote. When
    ``origin/HEAD`` was never pinned (older clones, a failed ``remote set-head``),
    fall back to ``origin/main`` / ``origin/master`` rather than silently cutting
    from the root's parked HEAD.
    """
    result = subprocess.run(
        ["git", "-C", project_root, "symbolic-ref", "--quiet",
         "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
    )
    ref = result.stdout.strip()
    if result.returncode == 0 and ref.startswith("refs/remotes/"):
        return ref.removeprefix("refs/remotes/")
    for candidate in ("origin/main", "origin/master"):
        exists = subprocess.run(
            ["git", "-C", project_root, "rev-parse", "--verify", "--quiet",
             f"refs/remotes/{candidate}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if exists.returncode == 0:
            return candidate
    return None


def _branch_exists(project_root: str, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", project_root, "rev-parse", "--verify", "--quiet",
             f"refs/heads/{branch}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def resolve_working_dir(
    project_root: str,
    agent_name: str,
    *,
    subdir: str | None = None,
    worktree_branch: str | None = None,
    reset_existing: bool = False,
) -> str:
    """Return (and, for worktrees, create) the agent's working directory.

    - ``subdir``: an existing/created subdirectory under the project root.
    - ``worktree_branch``: ``git worktree add <root>/<agent> <branch>``.
    - neither: the project root itself.

    ``reset_existing`` is set for spawn-derived ``agent/<name>`` branches: nobody owns
    a derived branch whose agent name is free again, so a stale leftover (from a
    deleted agent) is reset to the remote default tip with ``-B`` instead of being
    checked out as-is — otherwise a dead branch would silently shadow the remote's
    latest push. Operator-named branches keep checkout-as-is semantics (an in-flight
    branch must never be clobbered).
    """
    if subdir and worktree_branch:
        raise ValueError("pass at most one of subdir / worktree_branch")

    if worktree_branch:
        target = os.path.join(project_root, _slug(agent_name))
        if not _under(project_root, target):
            raise IsolationError(f"{target} escapes project root {project_root}")
        # `git worktree add <path> <branch>` only checks out an *existing* ref; a fresh
        # feature branch won't exist yet (spawn starts from the remote's latest state), so
        # create it with -b — from the remote default branch when the clone has one, so
        # the new branch starts at that tip regardless of where the root checkout is
        # parked (--no-track: the branch must not adopt the default branch as its
        # upstream, or the agent's plain `git push` would aim at it). An existing local
        # branch is checked out as-is; if it exists only on a remote, git DWIMs a
        # tracking branch from the bare `add`.
        start = _default_branch_start(project_root)
        cmd = ["git", "-C", project_root, "worktree", "add"]
        if _branch_exists(project_root, worktree_branch):
            if reset_existing and start:
                # -B fails when the branch is checked out in another worktree, which is
                # exactly the protection an in-flight agent needs.
                cmd += ["--no-track", "-B", worktree_branch, target, start]
            else:
                cmd += [target, worktree_branch]
        else:
            if start:
                cmd += ["--no-track", "-b", worktree_branch, target, start]
            else:
                cmd += ["-b", worktree_branch, target]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise WorktreeError(
                f"git worktree add for branch '{worktree_branch}' failed: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return target

    if subdir:
        target = os.path.join(project_root, subdir)
        if not _under(project_root, target):
            raise IsolationError(f"{target} escapes project root {project_root}")
        os.makedirs(target, exist_ok=True)
        return target

    return project_root
