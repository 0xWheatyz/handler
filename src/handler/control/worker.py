"""The control-container worker: executes commands the API enqueues.

The API (in its own container) has no ``git``/``tmux``/``claude`` and does not own the
tmux sessions, so it cannot run control actions directly. Instead it writes a ``queued``
row to the ``commands`` table; this worker — running in the control container — claims each
row, dispatches it to the *same* control functions the CLI uses (``spawn``/``poller``/
``skills_gen``/``repo.record_approval``), and writes the result or error back. It also runs
the periodic CI sweep, subsuming the old ``poll-ci --watch`` loop.

Every command runs in isolation: one bad command is recorded as ``failed`` and never stops
the loop. ``execute_command`` is the pure dispatch seam (given a claimed command dict,
returns a JSON-safe result or raises); ``drain``/``run`` are the claim+finish plumbing.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

from ..db import repository as repo
from ..db.engine import connection
from . import gitops, login, poller, reposync, skills_gen, spawn


class CommandError(Exception):
    """A command that cannot be executed (bad payload, missing target, …)."""


def _payload(command: dict) -> dict:
    return command.get("payload") or {}


def _cmd_spawn(command: dict) -> dict:
    p = _payload(command)
    name = command.get("agent_name") or p.get("name")
    if not command.get("project_id") or not name:
        raise CommandError("spawn requires project_id and an agent name")
    agent = spawn.spawn(
        command["project_id"],
        name,
        subdir=p.get("subdir") or p.get("dir"),
        worktree_branch=p.get("worktree"),
        task=p.get("task"),
        role=p.get("role"),
    )
    result = {
        "agent_id": agent["id"],
        "name": agent["name"],
        "working_dir": agent["working_dir"],
    }
    if agent.get("forge_note"):
        result["forge_note"] = agent["forge_note"]
    return result


def _cmd_kill(command: dict) -> dict:
    name = command.get("agent_name")
    if not command.get("project_id") or not name:
        raise CommandError("kill requires project_id and agent_name")
    spawn.kill(command["project_id"], name)
    return {"killed": name}


def _cmd_resume(command: dict) -> dict:
    name = command.get("agent_name")
    answer = _payload(command).get("answer")
    if not command.get("project_id") or not name:
        raise CommandError("resume requires project_id and agent_name")
    if not answer:
        raise CommandError("resume requires an 'answer' in the payload")
    with connection() as conn:
        agent = repo.get_agent_by_name(conn, command["project_id"], name)
    if agent is None:
        raise CommandError(f"agent '{name}' not found in project '{command['project_id']}'")
    ok, detail = spawn.resume(agent, answer)
    if ok:
        with connection() as conn:
            repo.set_agent_status(conn, agent["id"], "working")
    return {"resumed": ok, "detail": detail}


def _record_verdict(command: dict, status: str) -> dict:
    p = _payload(command)
    branch = p.get("branch")
    if not command.get("project_id") or not branch:
        raise CommandError(f"{status} requires project_id and a 'branch' in the payload")

    # Pin an approval to the reviewed commit so later pushes invalidate it. Prefer an
    # explicit sha; else read HEAD of the target agent's working dir (or the project root).
    approved_sha = p.get("sha")
    if approved_sha is None and status == "approved":
        with connection() as conn:
            working_dir = None
            if command.get("agent_name"):
                agent = repo.get_agent_by_name(conn, command["project_id"], command["agent_name"])
                working_dir = agent["working_dir"] if agent else None
            if working_dir is None:
                project = repo.get_project(conn, command["project_id"])
                working_dir = project["root_dir"] if project else None
        if working_dir:
            approved_sha = gitops.head_sha(working_dir)

    actor = command.get("requested_by") or "operator:web"
    with connection() as conn:
        approval = repo.record_approval(
            conn,
            project_id=command["project_id"],
            branch=branch,
            status=status,
            pr_ref=p.get("pr"),
            note=p.get("note"),
            approved_sha=approved_sha,
            actor=actor,
        )
    return {
        "approval_id": approval["id"],
        "branch": branch,
        "status": status,
        "approved_sha": approved_sha,
    }


def _cmd_approve(command: dict) -> dict:
    return _record_verdict(command, "approved")


def _cmd_reject(command: dict) -> dict:
    return _record_verdict(command, "rejected")


def _cmd_forge_init(command: dict) -> dict:
    project_id = command.get("project_id")
    if not project_id:
        raise CommandError("forge_init requires project_id")
    with connection() as conn:
        project = repo.get_project(conn, project_id)
    if project is None:
        raise CommandError(f"project '{project_id}' not registered")
    root = project["root_dir"]
    written = skills_gen.write_skills(root)
    result = {"written": len(written)}
    if not _payload(command).get("no_commit"):
        rel = os.path.join(".claude", "skills")
        ok_add, _ = gitops.add(root, [rel])
        ok_commit, out = gitops.commit(root, "chore: add handler forge-workflow skills")
        result["committed"] = bool(ok_add and ok_commit)
        if not result["committed"]:
            result["commit_note"] = out
    return result


# The prompt the bootstrap agent starts with when an operator ticks "Initialize mise" on
# the add-repo step. It launches with the [tasks.test] gate off (there's no .mise.toml yet)
# and the HANDLER_MISE_INIT marker on, so its hooks enforce the "commit + push" contract.
_MISE_INIT_TASK = (
    "This repository has no mise tooling yet. Detect the project's stack by inspecting the "
    "repo (e.g. package.json -> npm/pnpm/yarn, pyproject.toml or setup.py -> pytest, "
    "Cargo.toml -> cargo, go.mod -> go, a Makefile -> make, a Gemfile -> bundler), then "
    "write a `.mise.toml` at the repository root that pins the runtime under `[tools]` and "
    "defines a canonical `[tasks.test]` task running that stack's test command (add `lint` "
    "and `verify` tasks too when the stack has an obvious linter). Then commit the "
    "`.mise.toml` and push it to the remote. Do not finish until the change is committed AND "
    "pushed — the checkpoint gate will keep blocking otherwise."
)


def _cmd_mise_init(command: dict) -> dict:
    """Bootstrap mise tooling: launch an agent that writes, commits, and pushes a
    ``.mise.toml`` with a ``[tasks.test]`` task for the project's stack.

    Runs with ``require_tests=False`` (the project has no test task yet — creating one is
    the point) and ``mise_init=True`` (its hooks enforce the commit + push contract).
    """
    project_id = command.get("project_id")
    if not project_id:
        raise CommandError("mise_init requires project_id")
    p = _payload(command)
    name = command.get("agent_name") or p.get("name") or "mise-init"
    try:
        agent = spawn.spawn(
            project_id,
            name,
            task=p.get("task") or _MISE_INIT_TASK,
            require_tests=False,
            mise_init=True,
        )
    except spawn.SpawnError as exc:
        raise CommandError(str(exc)) from exc
    return {
        "agent_id": agent["id"],
        "name": agent["name"],
        "working_dir": agent["working_dir"],
    }


def _cmd_poll_ci(command: dict) -> dict:
    return poller.sweep(project_id=command.get("project_id"))


def _cmd_login_start(command: dict) -> dict:
    """Open the claude ``/login`` flow and return the claude.com authorization URL."""
    try:
        return login.start()
    except login.LoginError as exc:
        raise CommandError(str(exc)) from exc


def _cmd_login_submit(command: dict) -> dict:
    """Feed the pasted authorization code back into the live login session."""
    code = _payload(command).get("code")
    if not code:
        raise CommandError("login_submit requires a 'code' in the payload")
    try:
        result = login.submit_code(code)
    except login.LoginError as exc:
        raise CommandError(str(exc)) from exc
    if not result.get("success"):
        # Surface the pane tail so the operator can see why claude rejected the code.
        detail = result.get("output") or "claude did not confirm a successful login"
        raise CommandError(f"login not confirmed — {detail}")
    return result


def _cmd_sync(command: dict) -> dict:
    project_id = command.get("project_id")
    if not project_id:
        raise CommandError("sync requires project_id")
    with connection() as conn:
        project = repo.get_project(conn, project_id)
    if project is None:
        raise CommandError(f"project '{project_id}' not registered")
    try:
        return reposync.sync_project(project)
    except reposync.SyncError as exc:
        raise CommandError(str(exc)) from exc


_DISPATCH = {
    "spawn": _cmd_spawn,
    "kill": _cmd_kill,
    "resume": _cmd_resume,
    "approve": _cmd_approve,
    "reject": _cmd_reject,
    "forge_init": _cmd_forge_init,
    "mise_init": _cmd_mise_init,
    "poll_ci": _cmd_poll_ci,
    "sync": _cmd_sync,
    "login_start": _cmd_login_start,
    "login_submit": _cmd_login_submit,
}


def execute_command(command: dict) -> dict:
    """Dispatch a claimed command to its handler and return a JSON-safe result.

    Raises on any failure; the caller records that as a ``failed`` command. This is the
    pure seam tests exercise directly (with the tmux/gitops/forge/spawn.resume mocks).
    """
    handler = _DISPATCH.get(command["type"])
    if handler is None:  # pragma: no cover - CHECK constraint keeps types in the set
        raise CommandError(f"unknown command type '{command['type']}'")
    return handler(command)


def _run_one(command: dict) -> None:
    """Execute a claimed command and record done/failed — never raises."""
    try:
        result = execute_command(command)
        with connection() as conn:
            repo.finish_command(conn, command["id"], "done", result=result)
    except Exception as exc:  # noqa: BLE001 - one command must not kill the loop
        with connection() as conn:
            repo.finish_command(conn, command["id"], "failed", error=str(exc))


def fire_due_schedules(now: datetime | None = None) -> int:
    """Enqueue a spawn command for every schedule whose ``next_run_at`` has passed.

    Each firing becomes an ordinary queued ``spawn`` (visible in the Activity audit
    trail) with a timestamped agent name — ``<prefix>-YYYYMMDD-HHMMSS`` — so repeated
    runs never collide with the per-project name uniqueness. The schedule is advanced
    *before* the spawn executes: missed intervals collapse into a single run, and a
    failing spawn shows up as a failed command rather than a hot retry loop.
    """
    now = now or datetime.now(UTC)
    fired = 0
    with connection() as conn:
        due = repo.due_schedules(conn, now)
    for sched in due:
        name = f"{sched['name_prefix']}-{now.strftime('%Y%m%d-%H%M%S')}"
        payload: dict = {"task": sched["task"]}
        for key in ("role", "worktree", "subdir"):
            if sched.get(key):
                payload[key] = sched[key]
        with connection() as conn:
            command = repo.enqueue_command(
                conn,
                "spawn",
                project_id=sched["project_id"],
                agent_name=name,
                payload=payload,
                requested_by=f"schedule:{sched['id']}",
            )
            repo.mark_schedule_run(
                conn,
                sched["id"],
                last_run_at=now,
                next_run_at=now + timedelta(seconds=sched["interval_seconds"]),
                last_command_id=command["id"],
            )
        fired += 1
    return fired


def drain(worker_id: str, limit: int | None = None) -> int:
    """Claim and run queued commands until the queue is empty (or ``limit`` reached).

    Returns how many commands were processed. Each command is claimed in its own
    transaction, executed, then finished in another — so the claim is committed (visible as
    ``running``) before the potentially slow control action runs.
    """
    processed = 0
    while limit is None or processed < limit:
        with connection() as conn:
            command = repo.claim_next_command(conn, worker_id)
        if command is None:
            break
        _run_one(command)
        processed += 1
    return processed


def run(
    worker_id: str | None = None,
    poll_interval: float = 2.0,
    ci_interval: float = 30.0,
    iterations: int | None = None,
) -> None:
    """The control-container main loop: drain the command queue + sweep CI periodically.

    ``iterations`` bounds the loop for tests; production runs unbounded. Sleeps
    ``poll_interval`` only when a pass found no commands, so bursts drain promptly.
    """
    worker_id = worker_id or f"worker-{os.getpid()}"
    last_ci = 0.0
    count = 0
    while iterations is None or count < iterations:
        try:
            fire_due_schedules()
        except Exception:  # noqa: BLE001 - a schedule hiccup must not kill the worker
            pass
        did_work = drain(worker_id) > 0
        now = time.monotonic()
        if ci_interval > 0 and now - last_ci >= ci_interval:
            try:
                poller.sweep()
            except Exception:  # noqa: BLE001 - a CI sweep hiccup must not kill the worker
                pass
            last_ci = now
        count += 1
        if iterations is not None and count >= iterations:
            break
        if not did_work:
            time.sleep(poll_interval)
