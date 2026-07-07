"""Thin tmux wrapper — the single mock seam for spawning.

Every tmux/claude invocation goes through these functions so tests can substitute a
fake and never touch a real tmux server or ``claude`` binary.
"""

from __future__ import annotations

import subprocess

from ..config import get_settings


def session_name(project_id: str, agent_name: str) -> str:
    """``project__agent`` with tmux-illegal characters sanitized (README 3.4)."""
    safe = f"{project_id}__{agent_name}"
    for ch in (".", ":", " "):
        safe = safe.replace(ch, "-")
    return safe


def new_session(name: str, cwd: str, command: str, env: dict[str, str]) -> None:
    """Launch a detached tmux session running ``command`` in ``cwd`` with ``env`` set.

    ``tmux -e`` sets session environment, so the ``claude`` process (and therefore its
    hooks) inherit the agent identity + ``DATABASE_URL``.
    """
    tmux = get_settings().tmux_bin
    argv = [tmux, "new-session", "-d", "-s", name, "-c", cwd]
    for key, value in env.items():
        argv += ["-e", f"{key}={value}"]
    argv.append(command)
    subprocess.run(argv, check=True)


def has_session(name: str) -> bool:
    tmux = get_settings().tmux_bin
    result = subprocess.run(
        [tmux, "has-session", "-t", name],
        capture_output=True,
    )
    return result.returncode == 0


def list_sessions() -> list[str]:
    tmux = get_settings().tmux_bin
    result = subprocess.run(
        [tmux, "list-sessions", "-F", "#{session_name}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def kill_session(name: str) -> None:
    tmux = get_settings().tmux_bin
    subprocess.run([tmux, "kill-session", "-t", name], check=True)


def send_keys(name: str, keys: str) -> None:
    """Send a line of input to a live session (used by the resume seam)."""
    tmux = get_settings().tmux_bin
    subprocess.run([tmux, "send-keys", "-t", name, keys, "Enter"], check=True)
