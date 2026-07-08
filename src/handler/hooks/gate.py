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

from ..db import repository as repo
from . import verify
from .context import HookInput, Identity, emit

_GIT_PUSH = re.compile(r"\bgit\s+push\b")


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

    return _allow("tests and image build passed")


def handle(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    tool = hook_input.tool_name
    if tool == "AskUserQuestion":
        result = handle_ask_user_question(conn, ident, hook_input)
    elif tool == "Bash" and _GIT_PUSH.search(hook_input.tool_input.get("command", "")):
        result = handle_git_push(conn, ident, hook_input)
    else:
        # Not our concern — stay out of the way, let normal permission flow proceed.
        result = {}
    if result:
        emit(result)
    return result
