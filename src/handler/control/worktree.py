"""Per-agent working directory setup — a subdirectory under the project root, or a
git worktree. The isolation invariant: the resulting path is always under the project
root (README 3.4), never reaching into another project's tree.
"""

from __future__ import annotations

import os
import subprocess


class IsolationError(Exception):
    """Raised when a requested working dir would escape the project root."""


def _under(root: str, path: str) -> bool:
    root_abs = os.path.realpath(root)
    path_abs = os.path.realpath(path)
    return path_abs == root_abs or path_abs.startswith(root_abs + os.sep)


def resolve_working_dir(
    project_root: str,
    agent_name: str,
    *,
    subdir: str | None = None,
    worktree_branch: str | None = None,
) -> str:
    """Return (and, for worktrees, create) the agent's working directory.

    - ``subdir``: an existing/created subdirectory under the project root.
    - ``worktree_branch``: ``git worktree add <root>/<agent> <branch>``.
    - neither: the project root itself.
    """
    if subdir and worktree_branch:
        raise ValueError("pass at most one of subdir / worktree_branch")

    if worktree_branch:
        target = os.path.join(project_root, agent_name)
        if not _under(project_root, target):
            raise IsolationError(f"{target} escapes project root {project_root}")
        subprocess.run(
            ["git", "-C", project_root, "worktree", "add", target, worktree_branch],
            check=True,
        )
        return target

    if subdir:
        target = os.path.join(project_root, subdir)
        if not _under(project_root, target):
            raise IsolationError(f"{target} escapes project root {project_root}")
        os.makedirs(target, exist_ok=True)
        return target

    return project_root
