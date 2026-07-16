"""Thin ``git`` wrapper — the mock seam for the git operations Handler itself runs.

Handler runs git for a few narrow jobs: reading the current branch and HEAD sha (so the
push/approval gates know *what* is being pushed or merged), installing a credential
helper at spawn (README 3.7), and cloning/pulling a project's repo for the stateless
"always pull" workflow. Agents run their own git for the actual work; this seam is only
Handler's own use, kept behind one module so tests never touch a real repo.
"""

from __future__ import annotations

import os
import subprocess

from ..config import get_settings

_TIMEOUT = 30
# Clones and pulls move real data over the network; give them room.
_NETWORK_TIMEOUT = 600


def _run(
    args: list[str],
    cwd: str | None,
    env: dict[str, str] | None = None,
    timeout: int = _TIMEOUT,
) -> tuple[bool, str]:
    git = get_settings().git_bin
    run_env = None
    if env:
        run_env = {**os.environ, **env}
    try:
        result = subprocess.run(
            [git, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
        )
    except FileNotFoundError:
        return False, f"'{git}' not found"
    except subprocess.TimeoutExpired:
        return False, f"git {' '.join(args)} timed out"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output.strip()


def current_branch(cwd: str) -> str | None:
    ok, out = _run(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return out if ok and out else None


def head_sha(cwd: str) -> str | None:
    ok, out = _run(["rev-parse", "HEAD"], cwd)
    return out if ok and out else None


def config_local(cwd: str, key: str, value: str) -> tuple[bool, str]:
    """Set a repo-local git config key (used to install the credential helper)."""
    return _run(["config", "--local", key, value], cwd)


def is_clean(cwd: str) -> bool:
    """True when the working tree has no staged or unstaged changes."""
    ok, out = _run(["status", "--porcelain"], cwd)
    return ok and out == ""


def ahead_count(cwd: str) -> int | None:
    """Commits HEAD is ahead of its upstream, or ``None`` when no upstream is set.

    A ``None`` distinguishes "never pushed / no tracking branch" (the mise-init gate
    treats it as unpushed, prompting ``git push -u``) from "0 commits ahead" (pushed).
    """
    ok, out = _run(["rev-list", "--count", "@{upstream}..HEAD"], cwd)
    if not ok:
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


def add(cwd: str, paths: list[str]) -> tuple[bool, str]:
    return _run(["add", *paths], cwd)


def commit(cwd: str, message: str) -> tuple[bool, str]:
    return _run(["commit", "-m", message], cwd)


def is_repo(path: str) -> bool:
    """Whether ``path`` already holds a clone (cheap check, no subprocess)."""
    return os.path.isdir(os.path.join(path, ".git"))


def clone(
    remote: str,
    dest: str,
    env: dict[str, str] | None = None,
    config: list[tuple[str, str]] | None = None,
) -> tuple[bool, str]:
    """``git clone remote dest``, with optional one-shot ``-c key=value`` config.

    The ``-c`` config (e.g. the scoped credential helper) applies only to the clone
    command itself; persistent repo config is installed afterwards via
    :func:`config_local`.
    """
    args: list[str] = []
    for key, value in config or []:
        args += ["-c", f"{key}={value}"]
    args += ["clone", remote, dest]
    return _run(args, cwd=None, env=env, timeout=_NETWORK_TIMEOUT)


def pull_ff(cwd: str, env: dict[str, str] | None = None) -> tuple[bool, str]:
    """Fast-forward-only pull — never merges, so a diverged clone fails loudly."""
    return _run(["pull", "--ff-only"], cwd, env=env, timeout=_NETWORK_TIMEOUT)
