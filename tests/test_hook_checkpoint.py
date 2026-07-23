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


def _fake_git_state(monkeypatch, *, is_repo=True, clean=True, unpushed=0, has_origin=True):
    monkeypatch.setattr(gitops, "head_sha", lambda cwd: "abc123" if is_repo else None)
    monkeypatch.setattr(gitops, "is_clean", lambda cwd: clean)
    monkeypatch.setattr(gitops, "has_origin", lambda cwd: has_origin)
    monkeypatch.setattr(gitops, "unpushed_count", lambda cwd: unpushed)


def test_stop_blocks_on_failing_tests(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (False, "1 failed"))
    _fake_git_state(monkeypatch)

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result["decision"] == "block"
    assert "test suite is failing" in result["reason"]
    assert "1 failed" in result["reason"]

    cm = repo.get_checkmark(conn, ident.agent_id)
    assert cm["tests_status"] == "fail"
    assert cm["status"] == "blocked"
    # A blocked turn never records "done".
    assert repo.get_agent_by_name(conn, "p", "a")["status"] == "blocked"


def test_stop_blocks_on_uncommitted_changes_even_with_green_tests(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    _fake_git_state(monkeypatch, clean=False)

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result["decision"] == "block"
    assert "uncommitted" in result["reason"]

    cm = repo.get_checkmark(conn, ident.agent_id)
    assert cm["tests_status"] == "pass"  # tests still recorded honestly
    assert cm["status"] == "blocked"
    assert repo.get_agent_by_name(conn, "p", "a")["status"] == "blocked"


def test_stop_blocks_on_unpushed_commits(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    _fake_git_state(monkeypatch, unpushed=3)

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result["decision"] == "block"
    assert "3 commit(s) exist only locally" in result["reason"]
    assert repo.get_agent_by_name(conn, "p", "a")["status"] == "blocked"


def test_stop_reports_every_blocker_at_once(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (False, "boom"))
    _fake_git_state(monkeypatch, clean=False, unpushed=1)

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert "test suite is failing" in result["reason"]
    assert "uncommitted" in result["reason"]
    assert "exist only locally" in result["reason"]


def test_stop_skips_push_gate_without_an_origin_remote(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    # Local-only project: commits exist that no remote has, but there is no origin
    # to push them to — the push gate must not deadlock the agent.
    _fake_git_state(monkeypatch, unpushed=5, has_origin=False)

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result == {}
    assert repo.get_checkmark(conn, ident.agent_id)["status"] == "done"


def test_stop_allows_done_when_tests_pass_and_tree_is_settled(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    _fake_git_state(monkeypatch)

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result == {}  # no block

    cm = repo.get_checkmark(conn, ident.agent_id)
    assert cm["tests_status"] == "pass"
    assert cm["status"] == "done"
    assert cm["log_entry_id"] is not None


def test_stop_allows_done_when_working_dir_is_not_a_repo(conn, monkeypatch):
    # A manually managed root has nothing to gate beyond its tests.
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    _fake_git_state(monkeypatch, is_repo=False, clean=False, unpushed=9)

    result = checkpoint.handle_stop(conn, ident, HookInput({"session_id": "s1"}, "stop"))
    assert result == {}
    assert repo.get_checkmark(conn, ident.agent_id)["status"] == "done"


def test_stop_captures_final_message_as_checkpoint(conn, monkeypatch, tmp_path):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    _fake_git_state(monkeypatch)
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type": "user", "message": {"content": "do the thing"}}\n'
        "this line is not json\n"
        '{"type": "assistant", "message": {"content": [{"type": "text", '
        '"text": "Working on it."}]}}\n'
        '{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "x"},'
        ' {"type": "text", "text": "Shipped the fix in abc123; tests green."}]}}\n'
    )

    hi = HookInput({"session_id": "s1", "transcript_path": str(transcript)}, "stop")
    result = checkpoint.handle_stop(conn, ident, hi)
    assert result == {}
    cm = repo.get_checkmark(conn, ident.agent_id)
    # The webui checkpoint carries the agent's own closing message, captured
    # deterministically from the transcript — not left to the agent's discretion.
    assert cm["where_it_stopped"] == "Shipped the fix in abc123; tests green."


def test_blocked_stop_shows_blockers_not_narrative(conn, monkeypatch, tmp_path):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    _fake_git_state(monkeypatch, clean=False)
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type": "assistant", "message": {"content": [{"type": "text", '
        '"text": "All done!"}]}}\n'
    )

    hi = HookInput({"session_id": "s1", "transcript_path": str(transcript)}, "stop")
    checkpoint.handle_stop(conn, ident, hi)
    cm = repo.get_checkmark(conn, ident.agent_id)
    assert "uncommitted" in cm["where_it_stopped"]


def test_stop_does_not_reblock_when_already_active(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (False, "still failing"))
    _fake_git_state(monkeypatch)
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
