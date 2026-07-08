"""Stop / SessionEnd checkpoint gate."""

from __future__ import annotations

from handler.db import repository as repo
from handler.hooks import checkpoint, verify
from handler.hooks.context import HookInput, Identity


def _seed(conn):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "a", "/tmp/p/a")
    return Identity(a["id"], "p", "a", "/tmp/p/a")


def test_stop_blocks_on_failing_tests(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (False, "1 failed"))

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result["decision"] == "block"
    assert "test gate failed" in result["reason"]

    cm = repo.get_checkmark(conn, ident.agent_id)
    assert cm["tests_status"] == "fail"
    assert cm["status"] == "blocked"
    # A blocked turn never records "done".
    assert repo.get_agent_by_name(conn, "p", "a")["status"] == "blocked"


def test_stop_allows_done_on_passing_tests(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result == {}  # no block

    cm = repo.get_checkmark(conn, ident.agent_id)
    assert cm["tests_status"] == "pass"
    assert cm["status"] == "done"
    assert cm["log_entry_id"] is not None


def test_stop_does_not_reblock_when_already_active(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (False, "still failing"))
    hi = HookInput({"session_id": "s1", "stop_hook_active": True}, "stop")
    result = checkpoint.handle_stop(conn, ident, hi)
    assert result == {}  # recorded, but not an infinite block
    assert repo.get_checkmark(conn, ident.agent_id)["tests_status"] == "fail"


def test_session_end_records_without_gate(conn, monkeypatch):
    ident = _seed(conn)
    # Even if tests would fail, SessionEnd must not run the gate or block.
    monkeypatch.setattr(
        verify, "run_test", lambda cwd: (_ for _ in ()).throw(AssertionError("gate ran"))
    )
    result = checkpoint.handle_session_end(
        conn, ident, HookInput({"reason": "clear"}, "session_end")
    )
    assert result == {}
    assert repo.get_checkmark(conn, ident.agent_id)["where_it_stopped"].startswith(
        "session ended"
    )
