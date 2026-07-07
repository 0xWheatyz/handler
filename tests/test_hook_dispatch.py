"""The `python -m handler.hooks <event>` dispatch: stdin parsing + identity from env."""

from __future__ import annotations

import io

from handler.db import repository as repo
from handler.db.engine import get_engine
from handler.hooks import __main__ as hook_main
from handler.hooks import verify


def _seed(env):
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", "/tmp/p")
        return repo.create_agent(conn, "p", "a", "/tmp/p/a")


def test_dispatch_stop_via_stdin_and_env(env, monkeypatch, capsys):
    agent = _seed(env)
    monkeypatch.setenv("HANDLER_AGENT_ID", str(agent["id"]))
    monkeypatch.setenv("HANDLER_PROJECT_ID", "p")
    monkeypatch.setenv("HANDLER_AGENT_NAME", "a")
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    monkeypatch.setattr("sys.stdin", io.StringIO('{"session_id": "s1"}'))

    rc = hook_main.main(["stop"])
    assert rc == 0

    with get_engine().begin() as conn:
        assert repo.get_checkmark(conn, agent["id"])["tests_status"] == "pass"


def test_dispatch_unknown_event_is_usage_error(env):
    assert hook_main.main(["frobnicate"]) == 2


def test_dispatch_unresolvable_identity_returns_1(env, monkeypatch):
    monkeypatch.delenv("HANDLER_AGENT_ID", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO('{"cwd": "/nowhere"}'))
    assert hook_main.main(["stop"]) == 1
