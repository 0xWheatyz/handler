"""Phase 2 gate behavior: the hard approval gate + push CI-pending recording."""

from __future__ import annotations

from handler.db import repository as repo
from handler.hooks import gate, verify
from handler.hooks.context import HookInput, Identity


def _decision(result):
    return result["hookSpecificOutput"]["permissionDecision"]


def _seed(conn, role=None, name="deploy"):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", name, "/tmp/p/a", role=role)
    return Identity(a["id"], "p", name, "/tmp/p/a")


def _merge_input():
    return HookInput(
        {"tool_name": "Bash", "tool_input": {"command": "forge pr merge 7"}}, "pre_tool_use"
    )


def test_merge_denied_without_approval(conn, fake_gitops):
    ident = _seed(conn)
    result = gate.handle_merge_deploy(conn, ident, _merge_input())
    assert _decision(result) == "deny"
    assert "no standing approval" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_merge_denied_when_latest_is_rejected(conn, fake_gitops):
    ident = _seed(conn)
    other = repo.create_agent(conn, "p", "senior", "/tmp/p/s", role="senior")
    repo.record_approval(conn, "p", "feat/x", "rejected", other["id"])
    assert _decision(gate.handle_merge_deploy(conn, ident, _merge_input())) == "deny"


def test_merge_denied_on_self_approval(conn, fake_gitops):
    ident = _seed(conn)
    # Same agent approved the branch it now tries to merge — no self-approval.
    repo.record_approval(conn, "p", "feat/x", "approved", ident.agent_id)
    result = gate.handle_merge_deploy(conn, ident, _merge_input())
    assert _decision(result) == "deny"
    assert "different agent" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_merge_allowed_with_different_agent_approval(conn, fake_gitops):
    ident = _seed(conn)
    senior = repo.create_agent(conn, "p", "senior", "/tmp/p/s", role="senior")
    repo.record_approval(conn, "p", "feat/x", "approved", senior["id"])
    assert _decision(gate.handle_merge_deploy(conn, ident, _merge_input())) == "allow"


def test_deploy_task_is_also_gated(conn, fake_gitops):
    ident = _seed(conn)
    hi = HookInput(
        {"tool_name": "Bash", "tool_input": {"command": "mise run deploy"}}, "pre_tool_use"
    )
    # Routed through handle() to prove the matcher catches `mise run deploy`.
    result = gate.handle(conn, ident, hi)
    assert _decision(result) == "deny"


def test_merge_denied_when_branch_unknown(conn, fake_gitops):
    ident = _seed(conn)
    fake_gitops["branch"] = None
    result = gate.handle_merge_deploy(conn, ident, _merge_input())
    assert _decision(result) == "deny"
    assert "current git branch" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_merge_denied_when_approval_is_for_a_stale_commit(conn, fake_gitops):
    ident = _seed(conn)
    senior = repo.create_agent(conn, "p", "senior", "/tmp/p/s", role="senior")
    # Approved an earlier commit; HEAD has since moved on.
    repo.record_approval(conn, "p", "feat/x", "approved", senior["id"], approved_sha="oldsha")
    fake_gitops["sha"] = "newsha"
    result = gate.handle_merge_deploy(conn, ident, _merge_input())
    assert _decision(result) == "deny"
    assert "re-reviewed" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_merge_allowed_when_approved_sha_matches_head(conn, fake_gitops):
    ident = _seed(conn)
    senior = repo.create_agent(conn, "p", "senior", "/tmp/p/s", role="senior")
    fake_gitops["sha"] = "samesha"
    repo.record_approval(conn, "p", "feat/x", "approved", senior["id"], approved_sha="samesha")
    assert _decision(gate.handle_merge_deploy(conn, ident, _merge_input())) == "allow"


def test_push_records_ci_pending_on_allow(conn, fake_gitops, monkeypatch):
    ident = _seed(conn, name="junior")
    fake_gitops["branch"] = "feat/x"  # not protected -> no approval needed to push
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    monkeypatch.setattr(verify, "run_build", lambda cwd: (True, "built"))
    hi = HookInput({"tool_name": "Bash", "tool_input": {"command": "git push"}}, "pre_tool_use")
    result = gate.handle_git_push(conn, ident, hi)
    assert _decision(result) == "allow"
    # A pending-CI log entry was recorded for the pushed commit.
    pending = repo.get_pending_ci_entries(conn)
    assert len(pending) == 1
    assert pending[0]["push_sha"] == fake_gitops["sha"]


def test_direct_push_to_protected_branch_needs_approval(conn, fake_gitops, monkeypatch):
    # Closes the "merge locally, push to main" bypass around the forge-merge gate.
    ident = _seed(conn)
    fake_gitops["branch"] = "main"
    monkeypatch.setattr(verify, "run_test", lambda cwd: (True, "ok"))
    monkeypatch.setattr(verify, "run_build", lambda cwd: (True, "built"))
    hi = HookInput(
        {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}, "pre_tool_use"
    )
    result = gate.handle_git_push(conn, ident, hi)
    assert _decision(result) == "deny"
    assert "protected branch" in result["hookSpecificOutput"]["permissionDecisionReason"]
    # Nothing recorded as pending since the push was denied.
    assert repo.get_pending_ci_entries(conn) == []


def test_pr_title_mentioning_merge_is_not_gated(conn, fake_gitops):
    # The approval gate must not trip on a PR title/commit message containing "merge".
    ident = _seed(conn, name="junior")
    cmd = 'forge pr create --title "add merge helper"'
    hi = HookInput({"tool_name": "Bash", "tool_input": {"command": cmd}}, "pre_tool_use")
    assert gate.handle(conn, ident, hi) == {}
