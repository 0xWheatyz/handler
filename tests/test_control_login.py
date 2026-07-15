"""The claude web-login seam: navigating ``claude`` onboarding to the login URL, then
pasting the code and confirming the login.

Uses the shared ``fake_tmux`` fixture (extended here with a scripted ``capture_pane``) and
patches out the real sleeps + the on-disk credentials check, so no live claude/tmux/FS is
touched — the same approach as the spawn tests. Screen text mirrors the real claude 2.1
TUI captured during development.
"""

from __future__ import annotations

import pytest

from handler.control import login, tmux


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(login, "_sleep", lambda *_a, **_k: None)


@pytest.fixture
def stable_creds(monkeypatch):
    """No credentials change on disk — success must come from the pane/session signals."""
    monkeypatch.setattr(login, "_credentials_fingerprint", lambda: ())


def _panes(monkeypatch, *frames):
    """Make ``capture_pane`` return each frame in turn, then repeat the last one."""
    seq = list(frames)

    def capture(_name, escapes=False):
        return seq[0] if len(seq) == 1 else seq.pop(0)

    monkeypatch.setattr(tmux, "capture_pane", capture)


# A complete Claude OAuth URL (scheme + client_id + redirect_uri + state) — extraction
# deliberately rejects anything less, so the fixtures must use the real shape.
AUTH_URL = (
    "https://claude.com/cai/oauth/authorize?code=true&client_id=abc123&response_type=code"
    "&redirect_uri=https%3A%2F%2Fplatform.claude.com%2Foauth%2Fcode%2Fcallback"
    "&scope=user%3Aprofile&code_challenge=chal&code_challenge_method=S256&state=st42"
)
THEME_SCREEN = "Choose the text style that looks best with your terminal\n 1. Auto\n 2. Dark"
METHOD_SCREEN = "Select login method:\n 1. Claude account with subscription\n 2. Console account"
URL_SCREEN = f"Browser didn't open? Use the url below to sign in (c to copy)\n{AUTH_URL}"


# ---- URL extraction ----


def test_extract_url_prefers_complete_oauth_link():
    pane = f"Visit https://example.com/help or\n{AUTH_URL}\nand paste the code."
    assert login._extract_url(pane) == AUTH_URL


def test_extract_url_strips_trailing_punctuation():
    assert login._extract_url(f"Open ({AUTH_URL}).") == AUTH_URL


def test_extract_url_none_when_no_link():
    assert login._extract_url("no link here") is None


def test_extract_url_rejects_incomplete_url():
    assert login._extract_url("ttps://claude.com/cai/oauth/authorize?client_id=x") is None
    assert login._extract_url("https://claude.com/cai/oauth/authorize") is None


def test_extract_url_stops_at_box_border():
    assert login._extract_url(f"│{AUTH_URL}│") == AUTH_URL


def test_extract_url_recovers_href_from_osc8_hyperlink():
    # claude renders the URL as an OSC-8 hyperlink: the visible text can be styled/garbled
    # while the real href sits in the escape. Capturing with escapes lets us recover it.
    pane = f"\x1b]8;id=1;{AUTH_URL}\x1b\\click here\x1b]8;;\x1b\\"
    assert login._extract_url(pane) == AUTH_URL


# ---- start: onboarding navigation ----


def test_start_navigates_theme_then_method_to_the_url(env, fake_tmux, no_sleep, monkeypatch):
    # Fresh claude: theme picker → login-method menu → URL. Each unrecognized-as-URL screen
    # gets an Enter; the subscription option is the default so a bare Enter selects it.
    _panes(monkeypatch, THEME_SCREEN, METHOD_SCREEN, URL_SCREEN)

    result = login.start(url_timeout=5.0)

    assert result == {"session": login.LOGIN_SESSION, "url": AUTH_URL}
    launched = fake_tmux["calls"]["new_session"][0]
    assert launched["command"] == "claude"
    assert launched["width"] == login.LOGIN_COLS  # wide window, unclipped URL
    # Two Enters: accept the theme, then pick subscription. No blind "/login" typed into a
    # menu (that path is only for an already-onboarded REPL).
    assert len(fake_tmux["calls"]["send_enter"]) == 2
    assert fake_tmux["calls"]["send_keys"] == []
    assert login.LOGIN_SESSION in fake_tmux["live"]  # left alive for submit_code


def test_start_sends_login_when_already_onboarded_at_repl(env, fake_tmux, no_sleep, monkeypatch):
    # Already onboarded: no theme/method screen at first — a REPL. We send /login once,
    # which brings up the method menu, then select subscription.
    _panes(monkeypatch, "some repl prompt, ? for shortcuts", METHOD_SCREEN, URL_SCREEN)

    result = login.start(url_timeout=5.0)

    assert result["url"] == AUTH_URL
    assert [c["keys"] for c in fake_tmux["calls"]["send_keys"]] == ["/login"]
    assert len(fake_tmux["calls"]["send_enter"]) == 1  # subscription pick


def test_start_kills_a_stale_session_first(env, fake_tmux, no_sleep, monkeypatch):
    fake_tmux["live"].add(login.LOGIN_SESSION)
    _panes(monkeypatch, URL_SCREEN)

    login.start(url_timeout=5.0)

    assert login.LOGIN_SESSION in fake_tmux["calls"]["kill_session"]


def test_start_times_out_and_cleans_up_when_no_url(env, fake_tmux, no_sleep, monkeypatch):
    _panes(monkeypatch, "still thinking, no url yet")

    with pytest.raises(login.LoginError, match="timed out"):
        login.start(url_timeout=0.05, poll_interval=0.0, step_wait=0.0)

    assert login.LOGIN_SESSION not in fake_tmux["live"]


# ---- submit: paste + separate Enter, then confirm ----


def test_submit_pastes_code_then_sends_separate_enter(
    env, fake_tmux, no_sleep, stable_creds, monkeypatch
):
    fake_tmux["live"].add(login.LOGIN_SESSION)
    _panes(monkeypatch, "Login successful. Welcome back!")

    result = login.submit_code("a-long-authorization-code#state", poll_timeout=1.0)

    assert result["success"] is True
    # The code goes in as a *paste* (send_text), and Enter is a *separate* keystroke — the
    # fix for the long-code/Enter race that left the code unsubmitted.
    assert fake_tmux["calls"]["send_text"] == [
        {"name": login.LOGIN_SESSION, "text": "a-long-authorization-code#state"}
    ]
    assert fake_tmux["calls"]["send_enter"] == [{"name": login.LOGIN_SESSION}]
    assert login.LOGIN_SESSION not in fake_tmux["live"]  # torn down on success


def test_submit_confirmed_by_credentials_file(env, fake_tmux, no_sleep, monkeypatch):
    fake_tmux["live"].add(login.LOGIN_SESSION)
    # The pane never prints a success string, but claude writes its credentials — the
    # authoritative signal. First call = baseline, later calls = changed.
    calls = {"n": 0}

    def fingerprint():
        calls["n"] += 1
        return () if calls["n"] == 1 else (("~/.claude.json", 123, 45),)

    monkeypatch.setattr(login, "_credentials_fingerprint", fingerprint)
    _panes(monkeypatch, "still on the paste-code screen, no success text")

    result = login.submit_code("code", poll_timeout=1.0)

    assert result["success"] is True
    assert login.LOGIN_SESSION not in fake_tmux["live"]


def test_submit_fails_fast_on_oauth_error(env, fake_tmux, no_sleep, stable_creds, monkeypatch):
    fake_tmux["live"].add(login.LOGIN_SESSION)
    _panes(monkeypatch, "OAuth error: Request failed with status code 400\nPress Enter to retry.")

    result = login.submit_code("wrong", poll_timeout=5.0)

    assert result["success"] is False
    assert "OAuth error" in result["output"]
    assert login.LOGIN_SESSION in fake_tmux["live"]  # left up for a retry


def test_submit_without_session_raises(env, fake_tmux, no_sleep):
    with pytest.raises(login.LoginError, match="no active"):
        login.submit_code("code")


def test_submit_rejects_blank(env, fake_tmux, no_sleep):
    with pytest.raises(login.LoginError, match="no authorization code"):
        login.submit_code("   ")
