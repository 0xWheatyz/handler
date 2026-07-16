"""Stop / SessionEnd checkpoint gate."""

from __future__ import annotations

from handler.control import gitops, mise
from handler.db import repository as repo
from handler.hooks import checkpoint, verify
from handler.hooks.context import HookInput, Identity


def _seed(conn, mise_init=False):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "a", "/tmp/p/a")
    return Identity(a["id"], "p", "a", "/tmp/p/a", mise_init=mise_init)


def _fake_mise_state(monkeypatch, *, has_test, clean, ahead):
    monkeypatch.setattr(mise, "has_test_task", lambda cwd: has_test)
    monkeypatch.setattr(gitops, "is_clean", lambda cwd: clean)
    monkeypatch.setattr(gitops, "ahead_count", lambda cwd: ahead)


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


def test_mise_init_stop_blocks_when_no_test_task(conn, monkeypatch):
    ident = _seed(conn, mise_init=True)
    # The normal test gate must NOT run for a mise-init agent.
    monkeypatch.setattr(
        verify, "run_test", lambda cwd: (_ for _ in ()).throw(AssertionError("test gate ran"))
    )
    _fake_mise_state(monkeypatch, has_test=False, clean=True, ahead=0)

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result["decision"] == "block"
    assert "[tasks.test]" in result["reason"]
    assert repo.get_agent_by_name(conn, "p", "a")["status"] == "blocked"


def test_mise_init_stop_blocks_on_uncommitted_changes(conn, monkeypatch):
    ident = _seed(conn, mise_init=True)
    _fake_mise_state(monkeypatch, has_test=True, clean=False, ahead=0)
    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result["decision"] == "block"
    assert "uncommitted" in result["reason"]


def test_mise_init_stop_blocks_when_no_upstream(conn, monkeypatch):
    ident = _seed(conn, mise_init=True)
    _fake_mise_state(monkeypatch, has_test=True, clean=True, ahead=None)
    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result["decision"] == "block"
    assert "upstream" in result["reason"]


def test_mise_init_stop_blocks_on_unpushed_commits(conn, monkeypatch):
    ident = _seed(conn, mise_init=True)
    _fake_mise_state(monkeypatch, has_test=True, clean=True, ahead=2)
    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result["decision"] == "block"
    assert "not been pushed" in result["reason"]


def test_mise_init_stop_allows_when_committed_and_pushed(conn, monkeypatch):
    ident = _seed(conn, mise_init=True)
    _fake_mise_state(monkeypatch, has_test=True, clean=True, ahead=0)
    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result == {}  # contract met — the turn may end
    cm = repo.get_checkmark(conn, ident.agent_id)
    assert cm["status"] == "done"
    assert repo.get_agent_by_name(conn, "p", "a")["status"] == "done"


def test_mise_init_stop_does_not_reblock_when_already_active(conn, monkeypatch):
    ident = _seed(conn, mise_init=True)
    _fake_mise_state(monkeypatch, has_test=False, clean=True, ahead=0)
    hi = HookInput({"session_id": "s1", "stop_hook_active": True}, "stop")
    result = checkpoint.handle_stop(conn, ident, hi)
    assert result == {}  # recorded, but not an infinite block


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
