"""Generate the per-agent Claude Code ``settings.json`` that wires each hook event to
``python -m handler.hooks <event>``.

This is the declarative half of hook integration; the imperative half — the agent
identity and ``DATABASE_URL`` — is injected as environment via tmux (see
``control.spawn``), because hook stdin does not carry our identity.

The dashboard's Claude page feeds in here too: the operator's permission overrides and
plugins (``claude_config`` / ``claude_plugins`` rows) are merged over the env-configured
baseline on every generation, so a change in the web UI applies to the next launch of
every agent without a redeploy.
"""

from __future__ import annotations

import json
import os
import re
import sys

from sqlalchemy import Connection

from ..config import get_settings
from ..db import repository as repo
from ..db.engine import connection

_OWNER_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


def _hook_command(event: str) -> str:
    # Use the exact interpreter the control layer runs under, so the hook resolves the
    # same handler package and virtualenv inside the tmux session.
    return f"{sys.executable} -m handler.hooks {event}"


def _marketplace_source(repo_ref: str) -> dict:
    """The settings-shaped source for a marketplace: ``owner/repo`` is a GitHub source,
    anything else is a git URL (the API validates it as one)."""
    if _OWNER_REPO_RE.match(repo_ref):
        return {"source": "github", "repo": repo_ref}
    return {"source": "git", "url": repo_ref}


def build_settings(conn: Connection | None = None) -> dict:
    settings = {
        "hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": _hook_command("stop")}]}],
            "SessionEnd": [
                {"hooks": [{"type": "command", "command": _hook_command("session_end")}]}
            ],
            "PreToolUse": [
                {
                    "matcher": "AskUserQuestion|Bash",
                    "hooks": [{"type": "command", "command": _hook_command("pre_tool_use")}],
                }
            ],
            "Notification": [
                {"hooks": [{"type": "command", "command": _hook_command("notification")}]}
            ],
        }
    }
    # ``claude -p`` never prompts — anything that would ask for permission is
    # auto-denied. The allowlist is therefore what lets normal work (git, mise, the
    # project's own tooling) proceed; the PreToolUse/Stop hooks above remain the hard
    # gate either way, since a hook deny overrides any allow.
    s = get_settings()
    mode = s.headless_permission_mode
    allow = list(s.headless_allowed_tools_list)
    deny: list[str] = []
    ask: list[str] = []
    plugins: list[dict] = []
    if conn is not None:
        stored = repo.get_claude_config(conn, "permissions") or {}
        if stored.get("default_mode"):
            mode = stored["default_mode"]
        allow += [r for r in stored.get("allow", []) if r not in allow]
        deny = list(stored.get("deny", []))
        ask = list(stored.get("ask", []))
        plugins = repo.list_claude_plugins(conn, enabled_only=True)
    permissions: dict = {"defaultMode": mode, "allow": allow}
    if deny:
        permissions["deny"] = deny
    if ask:
        permissions["ask"] = ask
    settings["permissions"] = permissions

    # Web-managed plugins: declaring the marketplace + the enabled plugin makes a
    # headless run install both on boot, no interactive `/plugin` flow needed.
    if plugins:
        settings["extraKnownMarketplaces"] = {
            p["marketplace"]: {"source": _marketplace_source(p["marketplace_repo"])}
            for p in plugins
        }
        settings["enabledPlugins"] = {
            f"{p['name']}@{p['marketplace']}": True for p in plugins
        }
    return settings


def write_settings(working_dir: str, conn: Connection | None = None) -> str:
    """Write ``.claude/settings.json`` under the agent's working dir; return its path.

    Opens a short read connection when the caller doesn't hold one — the web-managed
    permission overrides and plugins live in the database.
    """
    claude_dir = os.path.join(working_dir, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    path = os.path.join(claude_dir, "settings.json")
    if conn is None:
        with connection() as c:
            settings = build_settings(c)
    else:
        settings = build_settings(conn)
    with open(path, "w") as fh:
        json.dump(settings, fh, indent=2)
    return path
