"""PreToolUse: AskUserQuestion defer + git-push gate."""

from __future__ import annotations

from handler.control import gitops
from handler.db import repository as repo
from handler.hooks import gate, verify
from handler.hooks.context import HookInput, Identity


def _seed(conn, mise_init=False):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "a", "/tmp/p/a")
    return Identity(a["id"], "p", "a", "/tmp/p/a", mise_init=mise_init)


def _decision(result):
    return result["hookSpecificOutput"]["permissionDecision"]


def test_ask_user_question_is_deferred(conn):
    ident = _seed(conn)
    hi = HookInput(
        {
            "tool_name": "AskUserQuestion",
            "tool_input": {"questions": [{"question": "Which DB?"}]},
            "session_id": "s1",
        },
        "pre_tool_use",
    )
    result = gate.handle_ask_user_question(conn, ident, hi)
    assert _decision(result) == "deny"

    cm = repo.get_checkmark(conn, ident.agent_id)
    assert cm["status"] == "paused_for_input"
    assert cm["open_question"] == "Which DB?"
    assert repo.get_latest_open_question(conn, ident.agent_id)["question"] == "Which DB?"


def test_git_push_denied_when_tests_fail(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (False, "1 failed"))
    # Build must not even run when tests fail (cheap check first).
    monkeypatch.setattr(
        verify, "run_build", lambda cwd: (_ for _ in ()).throw(AssertionError("built"))
    )
    hi = HookInput(
        {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}},
        "pre_tool_use",
    )
    result = gate.handle_git_push(conn, ident, hi)
    assert _decision(result) == "deny"
    assert repo.get_checkmark(conn, ident.agent_id)["tests_status"] == "fail"


def test_git_push_denied_when_build_fails(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    monkeypatch.setattr(verify, "run_build", lambda cwd: (False, "COPY failed"))
    hi = HookInput({"tool_name": "Bash", "tool_input": {"command": "git push"}}, "pre_tool_use")
    result = gate.handle_git_push(conn, ident, hi)
    assert _decision(result) == "deny"
    cm = repo.get_checkmark(conn, ident.agent_id)
    assert cm["tests_status"] == "pass"
    assert cm["build_status"] == "fail"


def test_git_push_allowed_when_both_pass(conn, monkeypatch):
    ident = _seed(conn)
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    monkeypatch.setattr(verify, "run_build", lambda cwd: (True, "built"))
    hi = HookInput({"tool_name": "Bash", "tool_input": {"command": "git push"}}, "pre_tool_use")
    result = gate.handle_git_push(conn, ident, hi)
    assert _decision(result) == "allow"


def test_mise_init_push_bypasses_test_gate(conn, monkeypatch):
    ident = _seed(conn, mise_init=True)
    # The mise-init agent pushes the .mise.toml it just wrote; the test/build gate must
    # not run (there may be no working suite yet), and the push is recorded + allowed.
    monkeypatch.setattr(
        verify, "run_test", lambda cwd: (_ for _ in ()).throw(AssertionError("test gate ran"))
    )
    monkeypatch.setattr(gitops, "head_sha", lambda cwd: "sha123456789")
    hi = HookInput(
        {"tool_name": "Bash", "tool_input": {"command": "git push -u origin main"},
         "session_id": "s1"},
        "pre_tool_use",
    )
    result = gate.handle_git_push(conn, ident, hi)
    assert _decision(result) == "allow"
    # The push is recorded in the log so the run shows it landed.
    entries = repo.get_log(conn, ident.agent_id, limit=10, offset=0)
    assert any(e["push_sha"] == "sha123456789" for e in entries)


def test_non_push_bash_is_ignored(conn):
    ident = _seed(conn)
    hi = HookInput({"tool_name": "Bash", "tool_input": {"command": "ls -la"}}, "pre_tool_use")
    assert gate.handle(conn, ident, hi) == {}
