"""Stop / SessionEnd — the checkpoint + verification gate (README 3.5).

On ``Stop`` the gate runs the project's own ``test`` task and blocks the turn on
failure, so a turn cannot end on a broken suite. The result feeds straight into the
schema: ``status = 'done'`` is only ever recorded alongside a passing test run — not a
claim taken on faith. ``SessionEnd`` cannot be blocked, so it just records a final
checkpoint with the end reason.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Connection

from ..db import repository as repo
from . import verify
from .context import HookInput, Identity, emit


def handle_stop(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    working_dir = ident.working_dir or hook_input.cwd or "."
    ok, output = verify.run_test(working_dir)
    now = datetime.now(UTC)

    status = "done" if ok else "blocked"
    tests_status = "pass" if ok else "fail"
    summary = "checkpoint: tests passed" if ok else "checkpoint blocked: tests failed"

    log_id = repo.insert_log_entry(
        conn,
        agent_id=ident.agent_id,
        status=status,
        session_id=hook_input.session_id,
        summary=summary,
        decisions=(output[-4000:] if output else None),
    )
    repo.upsert_checkmark_row(
        conn,
        agent_id=ident.agent_id,
        checkpoint_at=now,
        status=status,
        where_it_stopped=summary,
        log_entry_id=log_id,
        tests_status=tests_status,
        tested_at=now,
    )
    repo.set_agent_status(conn, ident.agent_id, status)

    if not ok:
        # Guard against an infinite block loop: if we already re-invoked once, record
        # the failure but let the turn end rather than blocking forever.
        if hook_input.stop_hook_active:
            return {}
        return {
            "decision": "block",
            "reason": (
                "The test gate failed; the turn cannot end on a broken suite. "
                f"`mise run test` output:\n{output[-4000:]}"
            ),
        }
    return {}


def handle_session_end(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    now = datetime.now(UTC)
    reason = hook_input.reason or "session ended"
    log_id = repo.insert_log_entry(
        conn,
        agent_id=ident.agent_id,
        status="blocked",
        session_id=hook_input.session_id,
        summary=f"session ended: {reason}",
    )
    # Record the checkpoint but do not run the gate (the session is already ending).
    existing = repo.get_checkmark(conn, ident.agent_id)
    status = existing["status"] if existing else "blocked"
    repo.upsert_checkmark_row(
        conn,
        agent_id=ident.agent_id,
        checkpoint_at=now,
        status=status,
        where_it_stopped=f"session ended: {reason}",
        log_entry_id=log_id,
    )
    return {}


def handle(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    if hook_input.event == "session_end":
        result = handle_session_end(conn, ident, hook_input)
    else:
        result = handle_stop(conn, ident, hook_input)
    emit(result)
    return result
