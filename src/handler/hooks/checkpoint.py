"""Stop / SessionEnd — the checkpoint + verification gate (README 3.5).

On ``Stop`` the gate runs the project's own ``test`` task and checks the working tree
deterministically: failing tests, uncommitted changes, or commits that exist only
locally each block the turn, so an agent cannot end on a broken suite or walk away
from work it never committed or pushed. ``status = 'done'`` is only ever recorded
alongside a passing gate — not a claim taken on faith. The agent's final message is
captured from the session transcript onto the checkmark, so the dashboard always has a
real checkpoint to show regardless of whether the agent thought to leave one.
``SessionEnd`` cannot be blocked, so it just records a final checkpoint with the end
reason.

One narrow exemption: a ``scout`` that ends with a clean tree skips the test run and
records ``tests_status = 'skipped'``. Scouts exist to look and hand findings on, so the
gate's promise — ``done`` means a test run passed for the work that shipped — is vacuous
when nothing shipped, and a scheduled watch is mostly quiet runs. A dirty tree, or any
other role, keeps the full gate.
"""

from __future__ import annotations

import json
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


def _completion_blockers(working_dir: str) -> list[str]:
    """The commit/push half of the completion gate — ``[]`` when the tree is settled.

    Deterministic checks against git itself, not the agent's account of its work: a
    dirty tree means work was never committed; commits no ``origin/*`` ref contains
    mean work was never pushed. A working dir that isn't a git checkout (manually
    managed roots, empty repos) has nothing to gate.
    """
    if gitops.head_sha(working_dir) is None:
        return []
    blockers = []
    if not gitops.is_clean(working_dir):
        blockers.append("there are uncommitted changes — commit your work")
    if gitops.has_origin(working_dir):
        unpushed = gitops.unpushed_count(working_dir)
        if unpushed:
            blockers.append(
                f"{unpushed} commit(s) exist only locally — push them "
                "(`git push -u origin <branch>`)"
            )
    return blockers


def _tests_are_moot(ident: Identity, working_dir: str) -> bool:
    """True when this stop needs no test run: a ``scout`` leaving a clean tree.

    Scouts read the world and hand findings on; the expensive half of the gate exists to
    stop unverified *changes* reaching ``done``. Running the suite on every quiet watch
    run is pure overhead, and on a scheduled watch there are a lot of quiet runs. Any
    other role, or any uncommitted change, keeps the full gate.
    """
    if ident.role != "scout":
        return False
    return gitops.head_sha(working_dir) is None or gitops.is_clean(working_dir)


def _final_assistant_text(transcript_path: str | None) -> str | None:
    """The agent's last assistant message from the session transcript.

    Captured deterministically so the dashboard's checkpoint never depends on the
    agent remembering to file one. Returns ``None`` when there is no transcript or no
    text in it; never raises.
    """
    if not transcript_path:
        return None
    try:
        fh = open(transcript_path, encoding="utf-8")
    except OSError:
        return None
    last = None
    with fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") != "assistant":
                continue
            content = (entry.get("message") or {}).get("content")
            if isinstance(content, str):
                texts = [content]
            elif isinstance(content, list):
                texts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
            else:
                continue
            text = "\n".join(t for t in texts if t).strip()
            if text:
                last = text
    return last


def handle_stop(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    if ident.mise_init:
        return handle_mise_init_stop(conn, ident, hook_input)
    working_dir = ident.working_dir or hook_input.cwd or "."
    if _tests_are_moot(ident, working_dir):
        # A scout that touched nothing has nothing to verify: the gate's promise is
        # "``done`` means a test run passed for the work that shipped", and no work
        # shipped. The clean-tree condition is what keeps that honest — a scout that
        # *did* edit files falls through to the normal gate like anyone else.
        tests_ok, output, tests_status = True, "", "skipped"
    else:
        tests_ok, output = verify.run_test(working_dir)
        tests_status = "pass" if tests_ok else "fail"
    blockers = [] if tests_ok else ["the test suite is failing (`mise run test`)"]
    blockers += _completion_blockers(working_dir)
    now = datetime.now(UTC)

    status = "done" if not blockers else "blocked"
    summary = (
        (
            "checkpoint: nothing to ship, tests not applicable"
            if tests_status == "skipped"
            else "checkpoint: tests passed, work committed and pushed"
        )
        if not blockers
        else "checkpoint blocked: " + "; ".join(blockers)
    )
    # A done agent's checkmark carries its own closing message — the substance the
    # dashboard shows; a blocked one carries the blockers (the next turn will re-capture
    # the narrative once the gate clears). A harness that passes the text directly (pi)
    # wins over the claude-transcript parse.
    final_text = hook_input.final_assistant_text or _final_assistant_text(
        hook_input.transcript_path
    )
    where_it_stopped = final_text[:4000] if not blockers and final_text else summary

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
        where_it_stopped=where_it_stopped,
        log_entry_id=log_id,
        tests_status=tests_status,
        tested_at=now,
    )
    repo.set_agent_status(conn, ident.agent_id, status)

    if blockers:
        # Guard against an infinite block loop: if we already re-invoked once, record
        # the failure but let the turn end rather than blocking forever.
        if hook_input.stop_hook_active:
            return {}
        reason = (
            "The completion gate failed — an agent is only done when its tests pass "
            "and its work is committed and pushed. Blockers:\n- " + "\n- ".join(blockers)
        )
        if not tests_ok:
            reason += f"\n\n`mise run test` output:\n{output[-4000:]}"
        return {"decision": "block", "reason": reason}
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
