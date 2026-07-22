"""Generate the per-agent Claude Code ``settings.json`` that wires each hook event to
``python -m handler.hooks <event>``.

This is the declarative half of hook integration; the imperative half — the agent
identity and ``DATABASE_URL`` — is injected as environment via tmux (see
``control.spawn``), because hook stdin does not carry our identity.
"""

from __future__ import annotations

import json
import os
import sys

from ..config import get_settings


def _hook_command(event: str) -> str:
    # Use the exact interpreter the control layer runs under, so the hook resolves the
    # same handler package and virtualenv inside the tmux session.
    return f"{sys.executable} -m handler.hooks {event}"


def build_settings(headless: bool = False) -> dict:
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
    if headless:
        # ``claude -p`` never prompts — anything that would ask for permission is
        # auto-denied. The allowlist is therefore what lets normal work (git, mise, the
        # project's own tooling) proceed; the PreToolUse/Stop hooks above remain the hard
        # gate either way, since a hook deny overrides any allow.
        s = get_settings()
        settings["permissions"] = {
            "defaultMode": s.headless_permission_mode,
            "allow": s.headless_allowed_tools_list,
        }
    return settings


def write_settings(working_dir: str, headless: bool = False) -> str:
    """Write ``.claude/settings.json`` under the agent's working dir; return its path."""
    claude_dir = os.path.join(working_dir, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    path = os.path.join(claude_dir, "settings.json")
    with open(path, "w") as fh:
        json.dump(build_settings(headless=headless), fh, indent=2)
    return path
