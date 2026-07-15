"""Drive the bundled ``claude`` binary's ``/login`` OAuth flow from the web UI.

The dashboard has no ``claude`` (it runs in the API container); the control container
does. So logging Claude Code in is a two-step control command, mirroring the answer/resume
handoff:

1. ``login_start`` opens an interactive ``claude`` session in a dedicated tmux window and
   navigates to the **Claude account with subscription** login, driving whatever screens a
   fresh claude shows first (theme picker, folder-trust, the login-method menu) until the
   ``claude.com`` authorization URL appears. That URL is returned to the UI (which opens it
   in an iframe) and the tmux session is *left alive*.
2. ``login_submit`` pastes the authorization code the operator copies back, then presses
   Enter *separately* (a long code plus an immediate Enter races Ink and never submits),
   and confirms the login by watching for claude to write its credentials.

Everything shells out through the :mod:`~handler.control.tmux` seam, so the whole flow is
unit-testable with a fake tmux and never needs a real ``claude`` binary — the same pattern
the spawn/resume tests use.

The interactive claude TUI is timing-sensitive; the waits below are generous and
overridable. The navigation is screen-driven (it reads the pane and reacts) rather than a
fixed key sequence, so it survives a fresh-onboarding claude *and* an already-logged-out
one sitting at the REPL.
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

# Strip ANSI CSI + OSC escape sequences so screen-text matching sees plain text.
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
_FAILURE_HINTS = (
    "oauth error",
    "press enter to retry",
    "invalid code",
    "authentication failed",
    "login failed",
    "code is invalid",
    "expired",
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

    Requiring the scheme + the OAuth query markers rejects a mid-render capture (dropped
    scheme chars, or a URL cut before its query string) — handing either to the iframe
    would send the operator to a broken page.
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

    Claude Code stores its OAuth account/token under the user's home — on Linux in
    ``~/.claude.json`` (and/or ``~/.claude/.credentials.json``); the exact filename has
    drifted across versions, so we watch every likely location. The fingerprint is
    ``(path, mtime_ns, size)`` tuples — it changes when a login writes the credentials,
    a far more reliable "did it work" signal than scraping the TUI for a success string.
    """
    home = _home()
    paths = {
        os.path.join(home, ".claude.json"),
        os.path.join(home, ".claude", ".credentials.json"),
        os.path.join(home, ".claude", "credentials.json"),
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


# ---- screen recognizers (matched against the ANSI-stripped, lower-cased pane) ----


def _is_login_method_screen(text: str) -> bool:
    return "select login method" in text or ("subscription" in text and "console account" in text)


def _is_theme_screen(text: str) -> bool:
    return "text style" in text or "choose the text" in text


def _is_trust_screen(text: str) -> bool:
    return "do you trust" in text or ("trust" in text and "files in this" in text)


def _is_continue_screen(text: str) -> bool:
    return "press enter to continue" in text


def start(
    *,
    boot_wait: float = 6.0,
    url_timeout: float = 60.0,
    step_wait: float = 1.5,
    poll_interval: float = 1.0,
) -> dict:
    """Open ``claude`` in tmux, navigate to the subscription login, return the URL.

    Reads the pane each pass and reacts — accepts the theme picker, a folder-trust prompt,
    and any "press enter to continue"; selects the (default) subscription option on the
    login-method menu; sends ``/login`` once if claude is already onboarded and sitting at
    the REPL. Leaves the tmux session alive for :func:`submit_code`. Raises
    :class:`LoginError` if no complete authorization URL appears within ``url_timeout``.
    """
    claude = get_settings().claude_bin
    # A stale session from a previous, abandoned attempt would swallow our keystrokes.
    if tmux.has_session(LOGIN_SESSION):
        tmux.kill_session(LOGIN_SESSION)

    tmux.new_session(
        LOGIN_SESSION, cwd=_home(), command=claude, env={}, width=LOGIN_COLS, height=LOGIN_ROWS
    )
    _sleep(boot_wait)  # let claude finish its splash/boot and reach the first screen

    deadline = time.monotonic() + url_timeout
    tried_login = False
    url: str | None = None
    last_pane = ""
    while url is None and time.monotonic() < deadline:
        # Capture with escapes so an OSC-8 hyperlink href is recoverable; require a
        # *complete* URL so a still-rendering pane keeps us polling for a clean one.
        last_pane = tmux.capture_pane(LOGIN_SESSION, escapes=True)
        url = _extract_url(last_pane)
        if url is not None:
            break
        text = _strip_ansi(last_pane).lower()
        if _is_login_method_screen(text):
            tmux.send_enter(LOGIN_SESSION)  # subscription is the default (option 1)
        elif _is_theme_screen(text) or _is_trust_screen(text) or _is_continue_screen(text):
            tmux.send_enter(LOGIN_SESSION)  # accept the default and move on
        elif not tried_login:
            # Already-onboarded claude sitting at the REPL (or a screen we don't recognize):
            # ask for the login menu once, then let the recognizers above take over.
            tmux.send_keys(LOGIN_SESSION, "/login")
            tried_login = True
        else:
            _sleep(poll_interval)
            continue
        _sleep(step_wait)

    if url is None:
        # Surface what claude actually rendered so a wrong/blocked state is diagnosable.
        tail = _tail(_strip_ansi(last_pane))
        if tmux.has_session(LOGIN_SESSION):
            tmux.kill_session(LOGIN_SESSION)
        message = (
            "timed out waiting for a complete claude login URL — is the 'claude' binary "
            "installed in the control container and does '/login' reach the subscription flow?"
        )
        if tail:
            message += f" Last screen:\n{tail}"
        raise LoginError(message)
    return {"session": LOGIN_SESSION, "url": url}


def submit_code(
    code: str,
    *,
    settle_wait: float = 2.0,
    poll_timeout: float = 40.0,
    poll_interval: float = 1.0,
) -> dict:
    """Paste the authorization ``code`` into the live login session and confirm.

    Delivers the code as a paste and presses Enter **separately** after ``settle_wait`` —
    a long code plus an immediate Enter is processed before the paste registers, so nothing
    submits (the observed failure). Then polls (up to ``poll_timeout``) for success —
    claude's credentials file changing on disk (authoritative), a success line, or the
    session exiting — and fails fast on an OAuth-error screen. Returns
    ``{"success": bool, "output": <pane tail>}`` and kills the session on success. Raises
    :class:`LoginError` if there is no session to submit to.
    """
    code = (code or "").strip()
    if not code:
        raise LoginError("no authorization code provided")
    if not tmux.has_session(LOGIN_SESSION):
        raise LoginError("no active claude login session — start the login flow again")

    baseline = _credentials_fingerprint()
    tmux.send_text(LOGIN_SESSION, code)  # paste, no Enter
    _sleep(settle_wait)  # let Ink commit the paste before we submit it
    tmux.send_enter(LOGIN_SESSION)  # separate Enter — avoids the paste/Enter race

    deadline = time.monotonic() + poll_timeout
    success = False
    pane = ""
    while time.monotonic() < deadline:
        _sleep(poll_interval)
        pane = tmux.capture_pane(LOGIN_SESSION, escapes=True)
        stripped = _strip_ansi(pane)
        if _credentials_fingerprint() != baseline:
            success = True
            break
        if _looks_successful(stripped):
            success = True
            break
        if not tmux.has_session(LOGIN_SESSION):
            # claude exited on its own after a successful login.
            success = True
            break
        if _looks_failed(stripped):
            # claude rejected the code (expired/invalid); stop waiting and report it.
            break

    if success and tmux.has_session(LOGIN_SESSION):
        tmux.kill_session(LOGIN_SESSION)
    return {"success": success, "output": _tail(_strip_ansi(pane))}


def _looks_successful(pane: str) -> bool:
    low = (pane or "").lower()
    return any(hint in low for hint in _SUCCESS_HINTS)


def _looks_failed(pane: str) -> bool:
    low = (pane or "").lower()
    return any(hint in low for hint in _FAILURE_HINTS)


def _tail(pane: str, lines: int = 12) -> str:
    """The last few non-blank pane lines, for surfacing success/failure in the UI."""
    kept = [ln for ln in (pane or "").splitlines() if ln.strip()]
    return "\n".join(kept[-lines:])
