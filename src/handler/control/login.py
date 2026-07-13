"""Drive the bundled ``claude`` binary's ``/login`` OAuth flow from the web UI.

The dashboard has no ``claude`` (it runs in the API container); the control container
does. So logging Claude Code in is a two-step control command, mirroring the answer/resume
handoff:

1. ``login_start`` opens an interactive ``claude`` session in a dedicated tmux window,
   sends ``/login``, selects the **Claude account with subscription** option, and scrapes
   the pane for the ``claude.com`` / ``claude.ai`` authorization URL. The URL is returned
   to the UI (which opens it in an iframe) and the tmux session is *left alive*.
2. ``login_submit`` sends the authorization code the operator pastes back into that same
   still-alive session, then confirms the login by watching for claude to write its
   credentials file (with a success-text fallback).

Everything shells out through the :mod:`~handler.control.tmux` seam, so the whole flow is
unit-testable with a fake tmux and never needs a real ``claude`` binary — the same pattern
the spawn/resume tests use.

The interactive claude TUI is inherently timing-sensitive; the waits below are generous
and overridable so an operator can tune them for a slow host. If claude's first run shows
onboarding (theme/trust prompts) before the ``/login`` menu, bump ``boot_wait``.
"""

from __future__ import annotations

import glob
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

# Strip ANSI CSI + OSC escape sequences so success-text matching sees plain text.
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"  # CSI (colors, cursor moves)
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC (…terminated by BEL or ST)
    r"|\x1b[@-Z\\-_]"  # two-char escapes
)
# An http(s) URL. The class excludes whitespace, quotes, box-drawing glyphs the TUI may
# render flush against the link, *and* control/escape bytes — so a URL sitting inside an
# OSC-8 hyperlink escape (``\x1b]8;;<URL>\x1b\\``) is recovered cleanly, cut at the ESC.
_URL_RE = re.compile(r"https?://[^\s\"'<>`|\x00-\x1f─-╿]+")
_SUCCESS_HINTS = (
    "login successful",
    "logged in",
    "successfully authenticated",
    "authentication successful",
    "you are now logged in",
    "welcome back",
)


class LoginError(Exception):
    """Raised when the claude login flow cannot be started or completed."""


def _home() -> str:
    return os.path.expanduser("~") or "/tmp"


def _sleep(seconds: float) -> None:
    """Indirection so tests can patch out real waiting."""
    time.sleep(seconds)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def _is_complete_oauth_url(url: str) -> bool:
    """A *usable* Claude OAuth URL, not a partial/garbled capture.

    Requiring the scheme + the OAuth query markers rejects a mid-render capture like
    ``ttps://claude.com/cai/oauth?…`` (dropped scheme chars) or a URL cut before its
    query string — handing either to the iframe would send the operator to a broken page.
    """
    low = url.lower()
    return (
        low.startswith("https://")
        and "oauth" in low
        and "client_id=" in low
        and "redirect_uri=" in low
        and "state=" in low
    )


def _extract_url(pane: str) -> str | None:
    """Return the first *complete* OAuth URL found in a captured pane, else ``None``."""
    if not pane:
        return None
    for raw in _URL_RE.findall(pane):
        candidate = raw.rstrip(".,);]}>")
        if _is_complete_oauth_url(candidate):
            return candidate
    return None


def _credentials_fingerprint() -> tuple:
    """A fingerprint of claude's on-disk credentials, to detect a login writing them.

    Claude Code stores its OAuth credentials under the user's home; the exact filename has
    drifted across versions, so we watch every likely location and any ``*credential*``
    file under ``~/.claude``. The fingerprint is ``(path, mtime, size)`` tuples — it
    changes when a login creates or rewrites the credentials, which is a far more reliable
    "did it work" signal than scraping the TUI for a success string.
    """
    home = _home()
    paths = {
        os.path.join(home, ".claude", ".credentials.json"),
        os.path.join(home, ".claude", "credentials.json"),
        os.path.join(home, ".claude.json"),
        os.path.join(home, ".config", "claude", "credentials.json"),
    }
    paths.update(glob.glob(os.path.join(home, ".claude", "*credential*")))
    fp = []
    for p in sorted(paths):
        try:
            st = os.stat(p)
            fp.append((p, st.st_mtime_ns, st.st_size))
        except OSError:
            continue
    return tuple(fp)


def start(
    *,
    boot_wait: float = 6.0,
    menu_wait: float = 2.0,
    url_timeout: float = 45.0,
    poll_interval: float = 0.5,
) -> dict:
    """Open ``claude`` in tmux, drive ``/login`` to the subscription account, return the URL.

    Leaves the tmux session alive for :func:`submit_code`. Raises :class:`LoginError` if
    no complete authorization URL appears within ``url_timeout`` seconds.
    """
    claude = get_settings().claude_bin
    # A stale session from a previous, abandoned attempt would swallow our keystrokes.
    if tmux.has_session(LOGIN_SESSION):
        tmux.kill_session(LOGIN_SESSION)

    tmux.new_session(
        LOGIN_SESSION, cwd=_home(), command=claude, env={}, width=LOGIN_COLS, height=LOGIN_ROWS
    )
    _sleep(boot_wait)  # let claude finish its splash/boot and reach a prompt

    tmux.send_keys(LOGIN_SESSION, "/login")
    _sleep(menu_wait)
    # The login menu's first, default-highlighted option is the subscription account;
    # a bare Enter selects it (send_keys always appends Enter).
    tmux.send_keys(LOGIN_SESSION, "")
    _sleep(menu_wait)

    deadline = time.monotonic() + url_timeout
    url: str | None = None
    last_pane = ""
    while url is None and time.monotonic() < deadline:
        # Capture with escapes so an OSC-8 hyperlink href is recoverable; require a
        # *complete* URL so a still-rendering pane keeps us polling instead of returning
        # a garbled fragment.
        last_pane = tmux.capture_pane(LOGIN_SESSION, escapes=True)
        url = _extract_url(last_pane)
        if url is None:
            _sleep(poll_interval)
    if url is None:
        # Don't leave a half-driven session lying around on failure. Surface what claude
        # actually rendered so a wrong menu/onboarding state is diagnosable, not opaque.
        tail = _tail(_strip_ansi(last_pane))
        if tmux.has_session(LOGIN_SESSION):
            tmux.kill_session(LOGIN_SESSION)
        message = (
            "timed out waiting for a complete claude login URL — is the 'claude' binary "
            "installed in the control container and does '/login' open the subscription flow?"
        )
        if tail:
            message += f" Last screen:\n{tail}"
        raise LoginError(message)
    return {"session": LOGIN_SESSION, "url": url}


def submit_code(
    code: str,
    *,
    poll_timeout: float = 40.0,
    poll_interval: float = 1.0,
) -> dict:
    """Feed the pasted authorization ``code`` into the live login session and confirm.

    Confirms by polling (up to ``poll_timeout`` seconds) for any of: claude's credentials
    file changing on disk (the authoritative signal), a success line in the pane, or the
    session exiting cleanly. Returns ``{"success": bool, "output": <pane tail>}`` and kills
    the session on success. Raises :class:`LoginError` if there is no session to submit to.
    """
    code = (code or "").strip()
    if not code:
        raise LoginError("no authorization code provided")
    if not tmux.has_session(LOGIN_SESSION):
        raise LoginError("no active claude login session — start the login flow again")

    baseline = _credentials_fingerprint()
    tmux.send_keys(LOGIN_SESSION, code)

    deadline = time.monotonic() + poll_timeout
    success = False
    pane = ""
    while time.monotonic() < deadline:
        _sleep(poll_interval)
        pane = tmux.capture_pane(LOGIN_SESSION, escapes=True)
        if _credentials_fingerprint() != baseline:
            success = True
            break
        if _looks_successful(_strip_ansi(pane)):
            success = True
            break
        if not tmux.has_session(LOGIN_SESSION):
            # claude exited on its own after a successful login.
            success = True
            break

    if success and tmux.has_session(LOGIN_SESSION):
        tmux.kill_session(LOGIN_SESSION)
    return {"success": success, "output": _tail(_strip_ansi(pane))}


def _looks_successful(pane: str) -> bool:
    low = (pane or "").lower()
    return any(hint in low for hint in _SUCCESS_HINTS)


def _tail(pane: str, lines: int = 12) -> str:
    """The last few non-blank pane lines, for surfacing success/failure in the UI."""
    kept = [ln for ln in (pane or "").splitlines() if ln.strip()]
    return "\n".join(kept[-lines:])
