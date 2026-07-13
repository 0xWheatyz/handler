"""Drive the bundled ``claude`` binary's ``/login`` OAuth flow from the web UI.

The dashboard has no ``claude`` (it runs in the API container); the control container
does. So logging Claude Code in is a two-step control command, mirroring the answer/resume
handoff:

1. ``login_start`` opens an interactive ``claude`` session in a dedicated tmux window,
   sends ``/login``, selects the **Claude account with subscription** option, and scrapes
   the pane for the ``claude.com`` / ``claude.ai`` authorization URL. The URL is returned
   to the UI (which opens it in an iframe) and the tmux session is *left alive*.
2. ``login_submit`` sends the authorization code the operator pastes back into that same
   still-alive session, waits for claude to exchange it, and reports success.

Everything shells out through the :mod:`~handler.control.tmux` seam, so the whole flow is
unit-testable with a fake tmux and never needs a real ``claude`` binary — the same pattern
the spawn/resume tests use.

The interactive claude TUI is inherently timing-sensitive; the waits below are generous
and overridable so an operator can tune them for a slow host. If claude's first run shows
onboarding (theme/trust prompts) before the ``/login`` menu, bump ``boot_wait``.
"""

from __future__ import annotations

import os
import re
import time

from ..config import get_settings
from . import tmux

# One well-known session name: ``login_start`` (re)creates it, ``login_submit`` reuses it.
LOGIN_SESSION = "handler__login"

# A very wide, tall detached window so claude prints the (long) authorization URL on a
# single unclipped line — at the default 80 columns capture-pane reads it back truncated
# (missing redirect_uri/state), which is the whole point of failure otherwise.
LOGIN_COLS = 500
LOGIN_ROWS = 50

# Any http(s) URL in the pane; we then prefer the OAuth/authorize link among them. The
# character class stops at whitespace, quotes, and — importantly — box-drawing glyphs
# (U+2500–U+257F) the TUI may render flush against the link, so a bordered URL isn't
# captured with a trailing "│".
_URL_RE = re.compile(r"https?://[^\s\"'<>`|─-╿]+")
_OAUTH_HINTS = ("oauth", "authorize", "claude.ai", "claude.com", "console.anthropic")
_SUCCESS_HINTS = (
    "login successful",
    "logged in",
    "successfully authenticated",
    "authentication successful",
    "you are now logged in",
)


class LoginError(Exception):
    """Raised when the claude login flow cannot be started or completed."""


def _home() -> str:
    return os.path.expanduser("~") or "/tmp"


def _sleep(seconds: float) -> None:
    """Indirection so tests can patch out real waiting."""
    time.sleep(seconds)


def _extract_url(pane: str) -> str | None:
    """Pull the login URL out of a captured pane, preferring the OAuth link."""
    if not pane:
        return None
    candidates = [c.rstrip(".,);]") for c in _URL_RE.findall(pane)]
    for c in candidates:
        if any(hint in c.lower() for hint in _OAUTH_HINTS):
            return c
    return candidates[0] if candidates else None


def start(
    *,
    boot_wait: float = 4.0,
    menu_wait: float = 1.5,
    url_timeout: float = 30.0,
    poll_interval: float = 0.5,
) -> dict:
    """Open ``claude`` in tmux, drive ``/login`` to the subscription account, return the URL.

    Leaves the tmux session alive for :func:`submit_code`. Raises :class:`LoginError` if
    no authorization URL appears within ``url_timeout`` seconds.
    """
    claude = get_settings().claude_bin
    # A stale session from a previous, abandoned attempt would swallow our keystrokes.
    if tmux.has_session(LOGIN_SESSION):
        tmux.kill_session(LOGIN_SESSION)

    tmux.new_session(
        LOGIN_SESSION, cwd=_home(), command=claude, env={}, width=LOGIN_COLS, height=LOGIN_ROWS
    )
    _sleep(boot_wait)  # let claude boot to its prompt

    tmux.send_keys(LOGIN_SESSION, "/login")
    _sleep(menu_wait)
    # The login menu's first, default-highlighted option is the subscription account;
    # a bare Enter selects it (send_keys always appends Enter).
    tmux.send_keys(LOGIN_SESSION, "")
    _sleep(menu_wait)

    deadline = time.monotonic() + url_timeout
    url: str | None = None
    while url is None and time.monotonic() < deadline:
        url = _extract_url(tmux.capture_pane(LOGIN_SESSION))
        if url is None:
            _sleep(poll_interval)
    if url is None:
        # Don't leave a half-driven session lying around on failure.
        if tmux.has_session(LOGIN_SESSION):
            tmux.kill_session(LOGIN_SESSION)
        raise LoginError(
            "timed out waiting for the claude login URL — is the 'claude' binary installed "
            "in the control container and does '/login' open the subscription flow?"
        )
    return {"session": LOGIN_SESSION, "url": url}


def submit_code(code: str, *, settle_wait: float = 3.0) -> dict:
    """Feed the pasted authorization ``code`` into the live login session.

    Returns ``{"success": bool, "output": <pane tail>}``. Kills the session on success.
    Raises :class:`LoginError` if there is no active login session to submit to.
    """
    code = (code or "").strip()
    if not code:
        raise LoginError("no authorization code provided")
    if not tmux.has_session(LOGIN_SESSION):
        raise LoginError("no active claude login session — start the login flow again")

    tmux.send_keys(LOGIN_SESSION, code)
    _sleep(settle_wait)

    pane = tmux.capture_pane(LOGIN_SESSION)
    success = _looks_successful(pane)
    if success and tmux.has_session(LOGIN_SESSION):
        tmux.kill_session(LOGIN_SESSION)
    return {"success": success, "output": _tail(pane)}


def _looks_successful(pane: str) -> bool:
    low = (pane or "").lower()
    return any(hint in low for hint in _SUCCESS_HINTS)


def _tail(pane: str, lines: int = 12) -> str:
    """The last few non-blank pane lines, for surfacing success/failure in the UI."""
    kept = [ln for ln in (pane or "").splitlines() if ln.strip()]
    return "\n".join(kept[-lines:])
