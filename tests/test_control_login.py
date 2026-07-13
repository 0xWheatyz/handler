"""The claude web-login seam: driving ``claude /login`` through tmux and scraping the URL.

Uses the shared ``fake_tmux`` fixture (extended here with a scripted ``capture_pane``) and
patches out the real sleeps, so no live claude/tmux is touched — the same approach as the
spawn tests.
"""

from __future__ import annotations

import pytest

from handler.control import login, tmux


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(login, "_sleep", lambda *_a, **_k: None)


def _pane(monkeypatch, *frames):
    """Make ``capture_pane`` return each frame in turn, then repeat the last one."""
    seq = list(frames)

    def capture(_name):
        return seq[0] if len(seq) == 1 else seq.pop(0)

    monkeypatch.setattr(tmux, "capture_pane", capture)


AUTH_URL = "https://claude.ai/oauth/authorize?code=true&client_id=abc&state=xyz"


def test_extract_url_prefers_oauth_link():
    pane = f"Visit https://example.com/help or\n{AUTH_URL}\nand paste the code."
    assert login._extract_url(pane) == AUTH_URL


def test_extract_url_strips_trailing_punctuation():
    assert login._extract_url(f"Open ({AUTH_URL}).") == AUTH_URL


def test_extract_url_none_when_no_link():
    assert login._extract_url("no link here") is None


def test_start_launches_claude_selects_subscription_and_returns_url(
    env, fake_tmux, no_sleep, monkeypatch
):
    _pane(monkeypatch, "booting…", f"Open this URL to log in:\n{AUTH_URL}")

    result = login.start(url_timeout=1.0)

    assert result == {"session": login.LOGIN_SESSION, "url": AUTH_URL}
    # A fresh claude session was launched…
    launched = fake_tmux["calls"]["new_session"]
    assert len(launched) == 1
    assert launched[0]["name"] == login.LOGIN_SESSION
    assert launched[0]["command"] == "claude"
    # …then /login was sent, followed by a bare Enter selecting the subscription option.
    sent = [c["keys"] for c in fake_tmux["calls"]["send_keys"]]
    assert sent[:2] == ["/login", ""]
    # The session is left alive for submit_code.
    assert login.LOGIN_SESSION in fake_tmux["live"]


def test_start_kills_a_stale_session_first(env, fake_tmux, no_sleep, monkeypatch):
    fake_tmux["live"].add(login.LOGIN_SESSION)  # a leftover from an abandoned attempt
    _pane(monkeypatch, f"{AUTH_URL}")

    login.start(url_timeout=1.0)

    assert login.LOGIN_SESSION in fake_tmux["calls"]["kill_session"]


def test_start_times_out_and_cleans_up_when_no_url(env, fake_tmux, no_sleep, monkeypatch):
    _pane(monkeypatch, "still thinking, no url yet")

    with pytest.raises(login.LoginError, match="timed out"):
        login.start(url_timeout=0.05, poll_interval=0.0)

    # It shouldn't leave a half-driven session lying around.
    assert login.LOGIN_SESSION not in fake_tmux["live"]


def test_submit_code_sends_code_and_reports_success(env, fake_tmux, no_sleep, monkeypatch):
    fake_tmux["live"].add(login.LOGIN_SESSION)
    _pane(monkeypatch, "Login successful. Welcome back!")

    result = login.submit_code("my-auth-code")

    assert result["success"] is True
    assert "Login successful" in result["output"]
    assert {"name": login.LOGIN_SESSION, "keys": "my-auth-code"} in fake_tmux["calls"]["send_keys"]
    # A confirmed login tears the session down.
    assert login.LOGIN_SESSION not in fake_tmux["live"]


def test_submit_code_reports_failure_without_killing_session(
    env, fake_tmux, no_sleep, monkeypatch
):
    fake_tmux["live"].add(login.LOGIN_SESSION)
    _pane(monkeypatch, "Invalid code, please try again")

    result = login.submit_code("wrong")

    assert result["success"] is False
    assert login.LOGIN_SESSION in fake_tmux["live"]  # left up for a retry


def test_submit_code_without_session_raises(env, fake_tmux, no_sleep):
    with pytest.raises(login.LoginError, match="no active"):
        login.submit_code("code")


def test_submit_code_rejects_blank(env, fake_tmux, no_sleep):
    with pytest.raises(login.LoginError, match="no authorization code"):
        login.submit_code("   ")
