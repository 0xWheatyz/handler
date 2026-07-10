"""PreToolUse — defer AskUserQuestion, and gate ``git push`` (README 3.6).

Claude Code's PreToolUse matcher matches on ``tool_name`` only, so this hook is wired
for ``AskUserQuestion|Bash`` and inspects the command itself to decide what to do:

- ``AskUserQuestion``: there is no human at the tmux TTY, so the question is *deferred*
  — persisted to the log + checkmark and the tool call denied, handing control to the
  async answer/resume flow.
- ``Bash`` running ``git push``: run the verification chain (tests first, then the
  throwaway image build) and deny the push on the first failure, so a push already
  known to fail CI doesn't leave.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from sqlalchemy import Connection

from ..config import get_settings
from ..control import gitops
from ..db import repository as repo
from . import verify
from .context import HookInput, Identity, emit

_GIT_PUSH = re.compile(r"\bgit\s+push\b")
# Actions that ship code past review: a forge merge, or the canonical deploy task. Anchored
# to the actual subcommands so a PR title/commit message mentioning "merge" doesn't trip it.
_MERGE_DEPLOY = re.compile(r"\bforge\s+(?:pr\s+)?merge\b|\bmise\s+run\s+deploy\b")


def _deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _allow(reason: str = "") -> dict:
    out: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }
    return out


def _question_text(tool_input: dict) -> str:
    """Flatten an AskUserQuestion payload into a human-readable question string."""
    questions = tool_input.get("questions")
    if isinstance(questions, list) and questions:
        parts = []
        for q in questions:
            if isinstance(q, dict) and q.get("question"):
                parts.append(str(q["question"]))
        if parts:
            return "\n".join(parts)
    # Fall back to the whole payload so nothing is lost.
    return json.dumps(tool_input)


def handle_ask_user_question(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    question = _question_text(hook_input.tool_input)
    now = datetime.now(UTC)
    log_id = repo.insert_log_entry(
        conn,
        agent_id=ident.agent_id,
        status="paused_for_input",
        session_id=hook_input.session_id,
        summary="agent asked the operator a question",
        question=question,
    )
    repo.upsert_checkmark_row(
        conn,
        agent_id=ident.agent_id,
        checkpoint_at=now,
        status="paused_for_input",
        open_question=question,
        log_entry_id=log_id,
    )
    repo.set_agent_status(conn, ident.agent_id, "paused_for_input")
    return _deny(
        "Question deferred to the operator; answer it via the API "
        "(POST .../answer then POST .../resume)."
    )


def handle_git_push(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    working_dir = ident.working_dir or hook_input.cwd or "."
    now = datetime.now(UTC)

    # Cheap check first: tests. Only on success do we pay for the image build.
    tests_ok, tests_out = verify.run_test(working_dir)
    if not tests_ok:
        repo.upsert_checkmark_row(
            conn,
            agent_id=ident.agent_id,
            checkpoint_at=now,
            status="blocked",
            tests_status="fail",
            tested_at=now,
        )
        return _deny(f"Push blocked: tests failed.\n{tests_out[-3000:]}")

    build_ok, build_out = verify.run_build(working_dir)
    repo.upsert_checkmark_row(
        conn,
        agent_id=ident.agent_id,
        checkpoint_at=now,
        status="working",
        tests_status="pass",
        tested_at=now,
        build_status="pass" if build_ok else "fail",
        built_at=now,
    )
    if not build_ok:
        return _deny(f"Push blocked: image build failed.\n{build_out[-3000:]}")

    # A direct push to a protected branch ships code without going through a forge merge,
    # so it must clear the same approval gate — this closes the "merge locally, push main"
    # path around the review requirement.
    branch = gitops.current_branch(working_dir)
    sha = gitops.head_sha(working_dir)
    if branch in get_settings().protected_branch_set:
        ok, reason = _approval_ok(conn, ident, branch, sha)
        if not ok:
            return _deny(f"Push to protected branch blocked: {reason}")

    # The push is cleared to leave. Record the commit + mark CI pending so the poller
    # closes the loop on the authoritative CI verdict (README 3.6).
    if sha:
        repo.insert_log_entry(
            conn,
            agent_id=ident.agent_id,
            status="working",
            session_id=hook_input.session_id,
            summary=f"push cleared local gates: {sha[:12]}",
            push_sha=sha,
            ci_status="pending",
        )
    return _allow("tests and image build passed")


def _approval_ok(
    conn: Connection, ident: Identity, branch: str, current_sha: str | None
) -> tuple[bool, str]:
    """Shared approval check: a standing ``approved`` for ``branch``, by a *different*
    agent, still pinned to the current commit when the approval recorded a sha."""
    approval = repo.get_latest_approval(conn, ident.project_id, branch)
    if approval is None or approval["status"] != "approved":
        return False, (
            f"branch '{branch}' has no standing approval. A senior agent must approve it "
            "before it can be merged or deployed."
        )
    # No self-approval. A null approver id is an operator verdict from the dashboard — a
    # genuinely different party than any pushing agent — so it never trips this check.
    approver_id = approval.get("approved_by_agent_id")
    if approver_id is not None and approver_id == ident.agent_id:
        return False, (
            f"branch '{branch}' was approved by this same agent. Review must come from a "
            "different agent — no self-approval."
        )
    approved_sha = approval.get("approved_sha")
    if approved_sha and current_sha and approved_sha != current_sha:
        return False, (
            f"the approval for '{branch}' was for commit {approved_sha[:12]}, but HEAD is "
            f"now {current_sha[:12]}. The new commits must be re-reviewed."
        )
    if approver_id is not None:
        by = f"agent id={approver_id}"
    else:
        by = approval.get("actor") or "operator"
    return True, f"branch '{branch}' approved by {by}"


def handle_merge_deploy(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    """Hard approval gate: refuse to merge/deploy a branch without a standing approval.

    The approval must exist, be ``approved``, have been made by a *different* agent than
    the one now merging — so 'senior approves' is a genuine second context and an agent
    can't rubber-stamp its own work — and, when the approval pinned a commit, still match
    the current HEAD so post-review commits don't ride in on a stale approval.
    """
    working_dir = ident.working_dir or hook_input.cwd or "."
    branch = gitops.current_branch(working_dir)
    if branch is None:
        return _deny(
            "Approval gate: could not determine the current git branch, so this "
            "merge/deploy cannot be checked against an approval. Aborting."
        )
    ok, reason = _approval_ok(conn, ident, branch, gitops.head_sha(working_dir))
    return _allow(reason) if ok else _deny(f"Approval gate: {reason}")


def handle(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    tool = hook_input.tool_name
    command = hook_input.tool_input.get("command", "") if tool == "Bash" else ""
    if tool == "AskUserQuestion":
        result = handle_ask_user_question(conn, ident, hook_input)
    elif tool == "Bash" and _GIT_PUSH.search(command):
        result = handle_git_push(conn, ident, hook_input)
    elif tool == "Bash" and _MERGE_DEPLOY.search(command):
        result = handle_merge_deploy(conn, ident, hook_input)
    else:
        # Not our concern — stay out of the way, let normal permission flow proceed.
        result = {}
    if result:
        emit(result)
    return result
