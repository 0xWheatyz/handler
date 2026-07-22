"""Thin tmux wrapper — now used ONLY by the interactive ``/login`` flow.

Agent runs are headless (``control.headless``); the one thing that still genuinely
needs a TTY is driving claude's ``/login`` OAuth screens. Everything here goes through
subprocess so the login tests can substitute a fake and never touch a real tmux server.
"""

from __future__ import annotations

import subprocess

from ..config import get_settings


def new_session(
    name: str,
    cwd: str,
    command: str,
    env: dict[str, str],
    *,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Launch a detached tmux session running ``command`` in ``cwd`` with ``env`` set.

    ``tmux -e`` sets session environment, so the ``claude`` process (and therefore its
    hooks) inherit the agent identity + ``DATABASE_URL``. ``width``/``height`` size the
    detached window (``-x``/``-y``); the login flow uses a very wide window so ``claude``
    prints the full authorization URL on one line instead of clipping it at the default
    80 columns (which capture-pane would then read back truncated).
    """
    tmux = get_settings().tmux_bin
    argv = [tmux, "new-session", "-d", "-s", name, "-c", cwd]
    if width is not None:
        argv += ["-x", str(width)]
    if height is not None:
        argv += ["-y", str(height)]
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


def kill_session(name: str) -> None:
    tmux = get_settings().tmux_bin
    subprocess.run([tmux, "kill-session", "-t", name], check=True)


def send_keys(name: str, keys: str) -> None:
    """Type ``keys`` into a session followed by Enter (used by resume + menu nav)."""
    tmux = get_settings().tmux_bin
    subprocess.run([tmux, "send-keys", "-t", name, keys, "Enter"], check=True)


def send_text(name: str, text: str) -> None:
    """Deliver ``text`` to a session as a bracketed paste, with **no** trailing Enter.

    Loads the text into a dedicated tmux buffer and pastes it, so arbitrary content is
    delivered verbatim — characters ``send-keys`` would treat as key names are safe, and a
    long string can't lose its submit to a race (the classic failure: a code plus an
    immediate Enter, where the Enter is processed before the paste registers, so nothing is
    submitted). Submit afterwards with :func:`send_enter`.
    """
    tmux = get_settings().tmux_bin
    buf = "handler-login"
    subprocess.run([tmux, "set-buffer", "-b", buf, "--", text], check=True)
    subprocess.run([tmux, "paste-buffer", "-b", buf, "-p", "-d", "-t", name], check=True)


def send_enter(name: str) -> None:
    """Send a bare Enter to a session (e.g. submit a previously pasted line / pick a menu)."""
    tmux = get_settings().tmux_bin
    subprocess.run([tmux, "send-keys", "-t", name, "Enter"], check=True)


def capture_pane(name: str, escapes: bool = False) -> str:
    """Return the visible text of a session's pane.

    ``-p`` prints to stdout, ``-J`` joins wrapped lines so a long URL split across the
    pane width comes back on one logical line (the login flow relies on this to recover
    the claude.com authorization link). ``escapes=True`` adds ``-e`` to keep ANSI/OSC
    escape sequences — the login URL extractor uses this so it can also recover a URL that
    the TUI renders as an OSC-8 hyperlink (where the visible text differs from the href).
    Returns an empty string if the session is gone.
    """
    tmux = get_settings().tmux_bin
    argv = [tmux, "capture-pane", "-t", name, "-p", "-J"]
    if escapes:
        argv.append("-e")
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout
