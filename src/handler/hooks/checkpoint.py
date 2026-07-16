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

from ..control import gitops, mise
from ..db import repository as repo
from . import verify
from .context import HookInput, Identity, emit


def _mise_init_blocker(working_dir: str) -> str | None:
    """Why a mise-init agent may not finish yet — ``None`` once the contract is met.

    The bootstrap is complete only when ``.mise.toml`` defines ``[tasks.test]`` and that
    file is committed (clean tree) and pushed (no commits ahead of, and an, upstream).
    """
    if not mise.has_test_task(working_dir):
        return "no mise config (mise.toml / .mise.toml) defines a [tasks.test] task yet"
    if not gitops.is_clean(working_dir):
        return "there are uncommitted changes — commit the .mise.toml"
    ahead = gitops.ahead_count(working_dir)
    if ahead is None:
        return "the branch has no upstream yet — push it with `git push -u`"
    if ahead > 0:
        return f"{ahead} commit(s) have not been pushed to the remote"
    return None


def handle_mise_init_stop(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    """Stop gate for the mise-init bootstrap agent: block until the ``.mise.toml`` test
    task exists and is committed + pushed (not the normal ``mise run test`` gate — there
    may be no working suite yet, which is exactly what this agent is bootstrapping)."""
    working_dir = ident.working_dir or hook_input.cwd or "."
    now = datetime.now(UTC)
    blocker = _mise_init_blocker(working_dir)

    status = "done" if blocker is None else "blocked"
    summary = (
        "checkpoint: .mise.toml committed and pushed"
        if blocker is None
        else f"mise-init blocked: {blocker}"
    )
    log_id = repo.insert_log_entry(
        conn,
        agent_id=ident.agent_id,
        status=status,
        session_id=hook_input.session_id,
        summary=summary,
    )
    repo.upsert_checkmark_row(
        conn,
        agent_id=ident.agent_id,
        checkpoint_at=now,
        status=status,
        where_it_stopped=summary,
        log_entry_id=log_id,
    )
    repo.set_agent_status(conn, ident.agent_id, status)

    if blocker is not None:
        # Same infinite-block guard as the test gate: if we already re-invoked once,
        # record the state but let the turn end rather than looping forever.
        if hook_input.stop_hook_active:
            return {}
        return {
            "decision": "block",
            "reason": (
                f"mise initialization is not complete: {blocker}. Write a `.mise.toml` with "
                "a [tasks.test] task for this project's stack, commit it, and push it before "
                "finishing."
            ),
        }
    return {}


def handle_stop(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    if ident.mise_init:
        return handle_mise_init_stop(conn, ident, hook_input)
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
