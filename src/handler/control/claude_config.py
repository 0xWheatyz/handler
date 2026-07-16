"""Seed the user-level Claude Code config so a spawned agent never blocks on first-run
onboarding.

A freshly-installed ``claude`` opens an interactive setup — the theme picker, then a
"do you trust the files in this folder?" prompt — before it reaches the REPL. A spawned
agent runs detached in tmux with no human at the TTY, so it would sit on the theme picker
forever (the observed wedge: ``agents.status='working'`` while nothing happens). The
``/login`` flow drives those screens by hand; a spawned agent can't, so we mark onboarding
complete on disk *before* launching claude.

The write is a merge, never a clobber: ``~/.claude.json`` also holds the ``oauthAccount``
the login flow wrote, and losing that would log the agent out. We only fill in the keys
that gate first-run and leave everything else — including a theme the operator already
chose — untouched.
"""

from __future__ import annotations

import json
import os


def _home() -> str:
    return os.path.expanduser("~") or "/tmp"


def config_path(home: str | None = None) -> str:
    return os.path.join(home or _home(), ".claude.json")


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _atomic_write(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.handler.tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def ensure_onboarded(working_dir: str | None = None, home: str | None = None) -> str:
    """Mark Claude Code onboarding complete in ``~/.claude.json`` and (when given) trust
    ``working_dir``, so a detached agent boots straight to the REPL. Returns the path.

    Idempotent and merge-only: ``hasCompletedOnboarding`` is forced true (a stale ``false``
    from a half-finished run would otherwise re-trigger setup), while ``theme`` is only
    filled in when absent so an operator's chosen theme survives.
    """
    path = config_path(home)
    data = _load(path)

    data["hasCompletedOnboarding"] = True
    data.setdefault("theme", "dark")

    if working_dir:
        projects = data.get("projects")
        if not isinstance(projects, dict):
            projects = {}
        entry = projects.get(working_dir)
        if not isinstance(entry, dict):
            entry = {}
        # The per-directory trust prompt claude shows on first entry into a new folder.
        entry["hasTrustDialogAccepted"] = True
        entry.setdefault("hasCompletedProjectOnboarding", True)
        projects[working_dir] = entry
        data["projects"] = projects

    _atomic_write(path, data)
    return path
