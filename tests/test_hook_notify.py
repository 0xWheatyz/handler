"""Notification hook: webhook POST only when WEBHOOK_URL is set; log always written."""

from __future__ import annotations

import httpx
import respx

from handler.db import repository as repo
from handler.hooks import notify
from handler.hooks.context import HookInput, Identity


def _seed(conn):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "a", "/tmp/p/a")
    return Identity(a["id"], "p", "a", "/tmp/p/a")


def test_notify_noop_without_webhook(conn, env):
    ident = _seed(conn)
    hi = HookInput({"message": "needs input", "session_id": "s1"}, "notification")
    # WEBHOOK_URL is unset in the env fixture -> no HTTP call, but the log is recorded.
    notify.handle(conn, ident, hi)
    assert "notification: needs input" in repo.get_log(conn, ident.agent_id)[0]["summary"]


@respx.mock
def test_notify_posts_when_webhook_set(conn, env, monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://ntfy.example/topic")
    from handler import config

    config.get_settings.cache_clear()

    route = respx.post("https://ntfy.example/topic").mock(return_value=httpx.Response(200))
    ident = _seed(conn)
    hi = HookInput({"message": "hello", "session_id": "s1"}, "notification")
    notify.handle(conn, ident, hi)

    assert route.called
    sent = route.calls[0].request
    import json

    body = json.loads(sent.content)
    assert body["project"] == "p"
    assert body["agent"] == "a"
    assert body["message"] == "hello"
