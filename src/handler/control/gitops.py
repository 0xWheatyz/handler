"""Thin ``git`` wrapper — the mock seam for the git operations Handler itself runs.

Handler runs git for a few narrow, non-mutating-or-config-only jobs: reading the
current branch and HEAD sha (so the push/approval gates know *what* is being pushed or
merged), and installing a credential helper at spawn (README 3.7). Agents run their own
git for the actual work; this seam is only Handler's own use, kept behind one module so
tests never touch a real repo.
"""

from __future__ import annotations

import subprocess

from ..config import get_settings

_TIMEOUT = 30


def _run(args: list[str], cwd: str) -> tuple[bool, str]:
    git = get_settings().git_bin
    try:
        result = subprocess.run(
            [git, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
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


def add(cwd: str, paths: list[str]) -> tuple[bool, str]:
    return _run(["add", *paths], cwd)


def commit(cwd: str, message: str) -> tuple[bool, str]:
    return _run(["commit", "-m", message], cwd)
