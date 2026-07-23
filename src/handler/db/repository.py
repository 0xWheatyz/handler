"""Data-access layer — every read and every write, one statement per function.

Writer discipline (README 3.2 / 3.3): the backend (control layer + hooks) is the only
thing that writes agent/checkmark/log rows; the API only reads, plus the single
``update_log_answer`` backfill on resume, plus control-plane registration
(``create_project`` / ``create_agent``, which the API mirrors). This is enforced by
import convention — the API package imports only the read functions and
``update_log_answer``; control/hooks import the write functions. A single global token
means we can't enforce it at the DB-permission level, so it is a code-organization
guarantee.

All functions take a live :class:`~sqlalchemy.Connection`; timestamps are set here as
UTC-aware datetimes rather than relying on server defaults, so SQLite and Postgres
agree on the exact value.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, select

from .tables import (
    agent_events,
    agent_runs,
    agents,
    approvals,
    checkmarks,
    claude_config,
    claude_connectors,
    claude_plugins,
    claude_skill_files,
    claude_skills,
    commands,
    forge_hosts,
    log_entries,
    projects,
    runtime_secrets,
    schedules,
    session_archives,
    shared_context,
    workers,
)
from .upsert import upsert_checkmark


def _now() -> datetime:
    return datetime.now(UTC)


def _row_to_dict(row) -> dict[str, Any] | None:
    return dict(row._mapping) if row is not None else None


# --------------------------------------------------------------------------- reads


def list_projects(conn: Connection) -> list[dict]:
    rows = conn.execute(select(projects).order_by(projects.c.id)).all()
    return [dict(r._mapping) for r in rows]


def get_project(conn: Connection, project_id: str) -> dict | None:
    row = conn.execute(select(projects).where(projects.c.id == project_id)).first()
    return _row_to_dict(row)


def list_agents(conn: Connection, project_id: str) -> list[dict]:
    rows = conn.execute(
        select(agents).where(agents.c.project_id == project_id).order_by(agents.c.name)
    ).all()
    return [dict(r._mapping) for r in rows]


def get_agent_by_name(conn: Connection, project_id: str, name: str) -> dict | None:
    row = conn.execute(
        select(agents).where(agents.c.project_id == project_id, agents.c.name == name)
    ).first()
    return _row_to_dict(row)


def get_checkmark(conn: Connection, agent_id: int) -> dict | None:
    row = conn.execute(select(checkmarks).where(checkmarks.c.agent_id == agent_id)).first()
    return _row_to_dict(row)


def get_log(conn: Connection, agent_id: int, limit: int = 100, offset: int = 0) -> list[dict]:
    rows = conn.execute(
        select(log_entries)
        .where(log_entries.c.agent_id == agent_id)
        .order_by(log_entries.c.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [dict(r._mapping) for r in rows]


def get_latest_open_question(conn: Connection, agent_id: int) -> dict | None:
    """The most recent log entry that recorded a question and has no answer yet."""
    row = conn.execute(
        select(log_entries)
        .where(
            log_entries.c.agent_id == agent_id,
            log_entries.c.question.is_not(None),
            log_entries.c.answer.is_(None),
        )
        .order_by(log_entries.c.id.desc())
        .limit(1)
    ).first()
    return _row_to_dict(row)


def get_shared_log(conn: Connection, limit: int = 100, offset: int = 0) -> list[dict]:
    """Only entries an agent (or the operator) explicitly marked ``global``."""
    rows = conn.execute(
        select(log_entries)
        .where(log_entries.c.visibility == "global")
        .order_by(log_entries.c.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [dict(r._mapping) for r in rows]


def get_shared_context(conn: Connection) -> list[dict]:
    rows = conn.execute(select(shared_context).order_by(shared_context.c.key)).all()
    return [dict(r._mapping) for r in rows]


def get_shared_context_key(conn: Connection, key: str) -> dict | None:
    row = conn.execute(select(shared_context).where(shared_context.c.key == key)).first()
    return _row_to_dict(row)


def get_agent_by_id(conn: Connection, agent_id: int) -> dict | None:
    row = conn.execute(select(agents).where(agents.c.id == agent_id)).first()
    return _row_to_dict(row)


def get_latest_approval(conn: Connection, project_id: str, branch: str) -> dict | None:
    """The most recent approval/rejection for a branch — the deploy gate's input."""
    row = conn.execute(
        select(approvals)
        .where(approvals.c.project_id == project_id, approvals.c.branch == branch)
        .order_by(approvals.c.id.desc())
        .limit(1)
    ).first()
    return _row_to_dict(row)


def get_pending_ci_entries(
    conn: Connection, project_id: str | None = None, limit: int = 200
) -> list[dict]:
    """Log entries that recorded a push and still await a CI verdict (poller input).

    Joins through the agent so the poller knows which project/working-dir each push
    belongs to. Scoped to one project when ``project_id`` is given.
    """
    stmt = (
        select(
            log_entries.c.id,
            log_entries.c.push_sha,
            log_entries.c.ci_status,
            agents.c.id.label("agent_id"),
            agents.c.project_id,
            agents.c.working_dir,
        )
        .select_from(log_entries.join(agents, log_entries.c.agent_id == agents.c.id))
        .where(
            log_entries.c.ci_status == "pending",
            log_entries.c.push_sha.is_not(None),
        )
        .order_by(log_entries.c.id.asc())
        .limit(limit)
    )
    if project_id is not None:
        stmt = stmt.where(agents.c.project_id == project_id)
    rows = conn.execute(stmt).all()
    return [dict(r._mapping) for r in rows]


# -------------------------------------------------------------------------- writes


def create_project(
    conn: Connection,
    project_id: str,
    root_dir: str,
    git_remote: str | None = None,
    credential_ref: str | None = None,
) -> dict:
    conn.execute(
        projects.insert().values(
            id=project_id,
            root_dir=root_dir,
            git_remote=git_remote,
            credential_ref=credential_ref,
            created_at=_now(),
        )
    )
    return get_project(conn, project_id)


def create_agent(
    conn: Connection,
    project_id: str,
    name: str,
    working_dir: str,
    status: str = "working",
    role: str | None = None,
) -> dict:
    result = conn.execute(
        agents.insert().values(
            project_id=project_id,
            name=name,
            working_dir=working_dir,
            status=status,
            role=role,
            created_at=_now(),
        )
    )
    agent_id = result.inserted_primary_key[0]
    row = conn.execute(select(agents).where(agents.c.id == agent_id)).first()
    return dict(row._mapping)


def set_agent_status(conn: Connection, agent_id: int, status: str) -> None:
    conn.execute(agents.update().where(agents.c.id == agent_id).values(status=status))


def list_agents_by_status(conn: Connection, status: str) -> list[dict]:
    """Every agent in a given status, across all projects (the worker's capture input)."""
    rows = conn.execute(
        select(agents).where(agents.c.status == status).order_by(agents.c.id)
    ).all()
    return [dict(r._mapping) for r in rows]


def update_agent_output(conn: Connection, agent_id: int, output: str) -> None:
    """Store the latest tmux pane-tail snapshot for an agent (worker poll loop)."""
    conn.execute(
        agents.update()
        .where(agents.c.id == agent_id)
        .values(last_output=output, output_at=_now())
    )


def insert_log_entry(conn: Connection, agent_id: int, status: str, **fields: Any) -> int:
    values = {"agent_id": agent_id, "status": status, "created_at": _now(), **fields}
    result = conn.execute(log_entries.insert().values(**values))
    return result.inserted_primary_key[0]


def update_log_answer(conn: Connection, log_entry_id: int, answer: str) -> bool:
    """The one post-insert mutation on log_entries — the answer backfill on resume."""
    result = conn.execute(
        log_entries.update()
        .where(log_entries.c.id == log_entry_id)
        .values(answer=answer)
    )
    return result.rowcount > 0


def upsert_checkmark_row(conn: Connection, agent_id: int, **fields: Any) -> None:
    """Overwrite the agent's checkmark (see :func:`db.upsert.upsert_checkmark`)."""
    values = {"agent_id": agent_id, **fields}
    values.setdefault("checkpoint_at", _now())
    upsert_checkmark(conn, values)


def record_approval(
    conn: Connection,
    project_id: str,
    branch: str,
    status: str,
    approved_by_agent_id: int | None = None,
    pr_ref: str | None = None,
    note: str | None = None,
    approved_sha: str | None = None,
    actor: str | None = None,
) -> dict:
    """Insert an approval/rejection record for a branch.

    An agent verdict passes ``approved_by_agent_id``; an operator verdict from the
    dashboard passes ``actor`` (e.g. ``operator:web``) and leaves the agent id null. The
    deploy gate treats a null agent id as a genuinely different party than any pushing
    agent, so operator approvals satisfy the "no self-approval" rule.
    """
    result = conn.execute(
        approvals.insert().values(
            project_id=project_id,
            branch=branch,
            approved_sha=approved_sha,
            pr_ref=pr_ref,
            status=status,
            approved_by_agent_id=approved_by_agent_id,
            actor=actor,
            note=note,
            created_at=_now(),
        )
    )
    approval_id = result.inserted_primary_key[0]
    row = conn.execute(select(approvals).where(approvals.c.id == approval_id)).first()
    return dict(row._mapping)


def list_approvals(
    conn: Connection, project_id: str, branch: str | None = None, limit: int = 100
) -> list[dict]:
    """Approvals for a project (optionally one branch), newest first — the UI's view."""
    stmt = select(approvals).where(approvals.c.project_id == project_id)
    if branch is not None:
        stmt = stmt.where(approvals.c.branch == branch)
    rows = conn.execute(stmt.order_by(approvals.c.id.desc()).limit(limit)).all()
    return [dict(r._mapping) for r in rows]


def update_ci_status(conn: Connection, log_entry_id: int, ci_status: str) -> bool:
    """Backfill a resolved CI verdict onto the log entry that recorded the push."""
    result = conn.execute(
        log_entries.update()
        .where(log_entries.c.id == log_entry_id)
        .values(ci_status=ci_status, ci_checked_at=_now())
    )
    return result.rowcount > 0


def set_shared_context(conn: Connection, key: str, value: str, agent_id: int | None) -> dict:
    """Upsert one shared-context key (the one table every project implicitly trusts)."""
    dialect = conn.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as ins
    else:
        from sqlalchemy.dialects.sqlite import insert as ins

    stmt = ins(shared_context).values(
        key=key, value=value, set_by_agent_id=agent_id, updated_at=_now()
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"],
        set_={
            "value": stmt.excluded.value,
            "set_by_agent_id": stmt.excluded.set_by_agent_id,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    conn.execute(stmt)
    return get_shared_context_key(conn, key)


# --------------------------------------------------- projects & agents (web management)


def update_project(conn: Connection, project_id: str, **fields: Any) -> dict | None:
    """Patch a project's editable columns (root_dir / git_remote / credential_ref).

    Only known columns are applied; an empty patch is a no-op read. Returns the row.
    """
    allowed = {"root_dir", "git_remote", "credential_ref"}
    values = {k: v for k, v in fields.items() if k in allowed}
    if values:
        conn.execute(projects.update().where(projects.c.id == project_id).values(**values))
    return get_project(conn, project_id)


def _purge_agent_dependents(conn: Connection, agent_ids: list[int]) -> None:
    """Delete (or detach) everything that references the given agents, so the agent rows
    themselves can be removed without tripping a foreign key.

    ``shared_context`` is a *global* table keyed by ``key`` — its rows outlive any one
    agent, so we only null the ``set_by_agent_id`` attribution rather than delete them.
    ``checkmarks`` must go before ``log_entries`` (it carries an FK to ``log_entries`` via
    the ``use_alter`` cycle). Approvals authored by these agents go with them.
    """
    if not agent_ids:
        return
    conn.execute(
        shared_context.update()
        .where(shared_context.c.set_by_agent_id.in_(agent_ids))
        .values(set_by_agent_id=None)
    )
    conn.execute(approvals.delete().where(approvals.c.approved_by_agent_id.in_(agent_ids)))
    conn.execute(checkmarks.delete().where(checkmarks.c.agent_id.in_(agent_ids)))
    conn.execute(log_entries.delete().where(log_entries.c.agent_id.in_(agent_ids)))
    # Headless-runner rows: events reference runs, so they go first.
    conn.execute(agent_events.delete().where(agent_events.c.agent_id.in_(agent_ids)))
    conn.execute(agent_runs.delete().where(agent_runs.c.agent_id.in_(agent_ids)))
    conn.execute(session_archives.delete().where(session_archives.c.agent_id.in_(agent_ids)))


def delete_project(conn: Connection, project_id: str) -> bool:
    """Remove a project and everything scoped to it.

    Every project accumulates FK-referencing rows (at minimum the ``sync`` command queued
    at registration, plus each agent's log/checkmark history), so the bare project delete
    would violate ``commands``/``agents``/``approvals``/``schedules`` foreign keys. Clear
    the dependents in FK-safe order first: agent-owned rows, then ``schedules`` (which
    reference ``commands`` via ``last_command_id``), then the remaining project-scoped
    rows, then the agents, then the project itself.
    """
    agent_ids = [
        row[0]
        for row in conn.execute(
            select(agents.c.id).where(agents.c.project_id == project_id)
        ).all()
    ]
    _purge_agent_dependents(conn, agent_ids)
    conn.execute(schedules.delete().where(schedules.c.project_id == project_id))
    conn.execute(approvals.delete().where(approvals.c.project_id == project_id))
    conn.execute(commands.delete().where(commands.c.project_id == project_id))
    conn.execute(agents.delete().where(agents.c.project_id == project_id))
    result = conn.execute(projects.delete().where(projects.c.id == project_id))
    return result.rowcount > 0


def delete_agent(conn: Connection, project_id: str, name: str) -> bool:
    """Remove a single agent row, first clearing its log/checkmark/approval history so the
    ``log_entries``/``checkmarks``/``approvals`` foreign keys don't block the delete."""
    agent = get_agent_by_name(conn, project_id, name)
    if agent is None:
        return False
    _purge_agent_dependents(conn, [agent["id"]])
    result = conn.execute(
        agents.delete().where(agents.c.project_id == project_id, agents.c.name == name)
    )
    return result.rowcount > 0


# ------------------------------------------------------------- command queue / audit log


def enqueue_command(
    conn: Connection,
    type: str,
    *,
    project_id: str | None = None,
    agent_name: str | None = None,
    payload: dict | None = None,
    requested_by: str | None = None,
    target_worker: str | None = None,
) -> dict:
    """Insert a ``queued`` control command for the worker to pick up. Returns the row.

    ``target_worker`` pins the command to one worker id (used by login_submit, which must
    reach the container holding the live login tmux session); null = any worker.
    """
    result = conn.execute(
        commands.insert().values(
            project_id=project_id,
            agent_name=agent_name,
            type=type,
            payload=payload,
            status="queued",
            requested_by=requested_by,
            target_worker=target_worker,
            created_at=_now(),
        )
    )
    return get_command(conn, result.inserted_primary_key[0])


def get_command(conn: Connection, command_id: int) -> dict | None:
    row = conn.execute(select(commands).where(commands.c.id == command_id)).first()
    return _row_to_dict(row)


def list_commands(
    conn: Connection, project_id: str | None = None, limit: int = 100, offset: int = 0
) -> list[dict]:
    stmt = select(commands)
    if project_id is not None:
        stmt = stmt.where(commands.c.project_id == project_id)
    rows = conn.execute(
        stmt.order_by(commands.c.id.desc()).limit(limit).offset(offset)
    ).all()
    return [dict(r._mapping) for r in rows]


def claim_next_command(
    conn: Connection,
    worker_id: str,
    types_excluded: tuple[str, ...] = (),
) -> dict | None:
    """Atomically claim the oldest queued command, flipping it to ``running``.

    Postgres uses ``FOR UPDATE SKIP LOCKED`` so multiple workers never grab the same row;
    on SQLite (single writer per transaction) the guarded ``WHERE status='queued'`` update
    plus a rowcount check is enough. Returns the claimed row, or ``None`` when the queue is
    empty or another worker won the race.

    A command whose ``target_worker`` is set is only claimable by that worker (the login
    flow's two steps must land on the same container). ``types_excluded`` lets a worker
    with no free run slots skip claiming commands that would launch a new run, leaving
    them for a less-loaded worker.
    """
    sel = (
        select(commands.c.id)
        .where(
            commands.c.status == "queued",
            (commands.c.target_worker.is_(None)) | (commands.c.target_worker == worker_id),
        )
        .order_by(commands.c.id.asc())
        .limit(1)
    )
    if types_excluded:
        sel = sel.where(commands.c.type.not_in(types_excluded))
    if conn.dialect.name == "postgresql":
        sel = sel.with_for_update(skip_locked=True)
    row = conn.execute(sel).first()
    if row is None:
        return None
    command_id = row[0]
    result = conn.execute(
        commands.update()
        .where(commands.c.id == command_id, commands.c.status == "queued")
        .values(status="running", claimed_by=worker_id, claimed_at=_now())
    )
    if result.rowcount != 1:
        return None  # lost the race to another worker
    return get_command(conn, command_id)


def finish_command(
    conn: Connection,
    command_id: int,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    """Mark a claimed command ``done`` or ``failed`` with its result/error."""
    conn.execute(
        commands.update()
        .where(commands.c.id == command_id)
        .values(status=status, result=result, error=error, finished_at=_now())
    )


# ---------------------------------------------------------------- forge hosts (registry)


def list_hosts(conn: Connection) -> list[dict]:
    rows = conn.execute(select(forge_hosts).order_by(forge_hosts.c.hostname)).all()
    return [dict(r._mapping) for r in rows]


def get_host(conn: Connection, hostname: str) -> dict | None:
    row = conn.execute(
        select(forge_hosts).where(forge_hosts.c.hostname == hostname)
    ).first()
    return _row_to_dict(row)


def create_host(
    conn: Connection,
    hostname: str,
    forge_type: str,
    token_env_var: str | None = None,
    base_url: str | None = None,
    token_enc: str | None = None,
    ssh_public_key: str | None = None,
    ssh_private_key_enc: str | None = None,
) -> dict:
    conn.execute(
        forge_hosts.insert().values(
            hostname=hostname,
            forge_type=forge_type,
            token_env_var=token_env_var,
            base_url=base_url,
            token_enc=token_enc,
            ssh_public_key=ssh_public_key,
            ssh_private_key_enc=ssh_private_key_enc,
            created_at=_now(),
        )
    )
    return get_host(conn, hostname)


def update_host(conn: Connection, hostname: str, **fields: Any) -> dict | None:
    allowed = {
        "forge_type",
        "token_env_var",
        "base_url",
        "token_enc",
        "ssh_public_key",
        "ssh_private_key_enc",
    }
    values = {k: v for k, v in fields.items() if k in allowed}
    if values:
        conn.execute(
            forge_hosts.update().where(forge_hosts.c.hostname == hostname).values(**values)
        )
    return get_host(conn, hostname)


def delete_host(conn: Connection, hostname: str) -> bool:
    result = conn.execute(forge_hosts.delete().where(forge_hosts.c.hostname == hostname))
    return result.rowcount > 0


# ------------------------------------------------------------------ schedules (recurring)


def list_schedules(conn: Connection, project_id: str | None = None) -> list[dict]:
    stmt = select(schedules)
    if project_id is not None:
        stmt = stmt.where(schedules.c.project_id == project_id)
    rows = conn.execute(stmt.order_by(schedules.c.id)).all()
    return [dict(r._mapping) for r in rows]


def get_schedule(conn: Connection, schedule_id: int) -> dict | None:
    row = conn.execute(select(schedules).where(schedules.c.id == schedule_id)).first()
    return _row_to_dict(row)


def create_schedule(
    conn: Connection,
    project_id: str,
    name_prefix: str,
    task: str,
    interval_seconds: int,
    next_run_at: datetime,
    role: str | None = None,
    worktree: str | None = None,
    subdir: str | None = None,
    enabled: bool = True,
) -> dict:
    result = conn.execute(
        schedules.insert().values(
            project_id=project_id,
            name_prefix=name_prefix,
            task=task,
            role=role,
            worktree=worktree,
            subdir=subdir,
            interval_seconds=interval_seconds,
            enabled=enabled,
            next_run_at=next_run_at,
            created_at=_now(),
        )
    )
    return get_schedule(conn, result.inserted_primary_key[0])


def update_schedule(conn: Connection, schedule_id: int, **fields: Any) -> dict | None:
    allowed = {
        "name_prefix",
        "task",
        "role",
        "worktree",
        "subdir",
        "interval_seconds",
        "enabled",
        "next_run_at",
    }
    values = {k: v for k, v in fields.items() if k in allowed}
    if values:
        conn.execute(
            schedules.update().where(schedules.c.id == schedule_id).values(**values)
        )
    return get_schedule(conn, schedule_id)


def delete_schedule(conn: Connection, schedule_id: int) -> bool:
    result = conn.execute(schedules.delete().where(schedules.c.id == schedule_id))
    return result.rowcount > 0


def due_schedules(conn: Connection, now: datetime, limit: int = 50) -> list[dict]:
    """Enabled schedules whose ``next_run_at`` has passed — the worker's sweep input."""
    rows = conn.execute(
        select(schedules)
        .where(schedules.c.enabled == True, schedules.c.next_run_at <= now)  # noqa: E712
        .order_by(schedules.c.next_run_at.asc())
        .limit(limit)
    ).all()
    return [dict(r._mapping) for r in rows]


def mark_schedule_run(
    conn: Connection,
    schedule_id: int,
    last_run_at: datetime,
    next_run_at: datetime,
    last_command_id: int | None = None,
) -> None:
    """Advance a schedule after firing it (missed intervals collapse into one run)."""
    conn.execute(
        schedules.update()
        .where(schedules.c.id == schedule_id)
        .values(
            last_run_at=last_run_at, next_run_at=next_run_at, last_command_id=last_command_id
        )
    )


# ------------------------------------------------- headless runner (workers/runs/events)


def upsert_worker_heartbeat(
    conn: Connection,
    worker_id: str,
    *,
    hostname: str | None = None,
    pid: int | None = None,
    max_runs: int | None = None,
    active_runs: int | None = None,
) -> None:
    """Register a worker or refresh its heartbeat — the reaper's liveness signal."""
    now = _now()
    result = conn.execute(
        workers.update()
        .where(workers.c.id == worker_id)
        .values(
            hostname=hostname, pid=pid, max_runs=max_runs,
            active_runs=active_runs, heartbeat_at=now,
        )
    )
    if result.rowcount == 0:
        conn.execute(
            workers.insert().values(
                id=worker_id, hostname=hostname, pid=pid, max_runs=max_runs,
                active_runs=active_runs, started_at=now, heartbeat_at=now,
            )
        )


def list_stale_workers(conn: Connection, cutoff: datetime) -> list[dict]:
    """Workers whose heartbeat predates ``cutoff`` — reaper input."""
    rows = conn.execute(select(workers).where(workers.c.heartbeat_at < cutoff)).all()
    return [dict(r._mapping) for r in rows]


def delete_worker(conn: Connection, worker_id: str) -> bool:
    """Drop a (dead) worker's registry row after its runs have been settled."""
    result = conn.execute(workers.delete().where(workers.c.id == worker_id))
    return result.rowcount > 0


class RunConflictError(Exception):
    """The agent already has a ``running`` run — a second concurrent claude process on
    one session would corrupt its transcript."""


def create_run(
    conn: Connection, agent_id: int, session_id: str, worker_id: str, kind: str
) -> dict:
    """Open an ``agent_runs`` row for a launching headless invocation.

    Enforces **one running run per agent** atomically: two workers that both claimed a
    resume for the same agent must not both launch. The agent row is locked first on
    Postgres (``FOR UPDATE``) so concurrent transactions serialize; SQLite's single
    writer gives the same guarantee for free. Raises :class:`RunConflictError` if a
    running run already exists.
    """
    lock = select(agents.c.id).where(agents.c.id == agent_id)
    if conn.dialect.name == "postgresql":
        lock = lock.with_for_update()
    conn.execute(lock)
    existing = conn.execute(
        select(agent_runs.c.id)
        .where(agent_runs.c.agent_id == agent_id, agent_runs.c.status == "running")
        .limit(1)
    ).first()
    if existing is not None:
        raise RunConflictError(
            f"agent {agent_id} already has running run {existing[0]}"
        )
    result = conn.execute(
        agent_runs.insert().values(
            agent_id=agent_id,
            session_id=session_id,
            worker_id=worker_id,
            kind=kind,
            status="running",
            cancel_requested=False,
            started_at=_now(),
        )
    )
    return get_run(conn, result.inserted_primary_key[0])


def get_run(conn: Connection, run_id: int) -> dict | None:
    row = conn.execute(select(agent_runs).where(agent_runs.c.id == run_id)).first()
    return _row_to_dict(row)


def finish_run(
    conn: Connection,
    run_id: int,
    status: str,
    exit_code: int | None = None,
    result: dict | None = None,
) -> bool:
    """Close a run — only if still ``running``, so a reaper's ``crashed`` verdict and the
    supervisor's own exit reconciliation can race without the loser clobbering the winner."""
    res = conn.execute(
        agent_runs.update()
        .where(agent_runs.c.id == run_id, agent_runs.c.status == "running")
        .values(status=status, exit_code=exit_code, result=result, finished_at=_now())
    )
    return res.rowcount > 0


def request_run_cancel(conn: Connection, run_id: int) -> bool:
    """Flag a running run for cancellation; its owning supervisor polls and SIGTERMs."""
    result = conn.execute(
        agent_runs.update()
        .where(agent_runs.c.id == run_id, agent_runs.c.status == "running")
        .values(cancel_requested=True)
    )
    return result.rowcount > 0


def get_cancel_requested(conn: Connection, run_id: int) -> bool:
    row = conn.execute(
        select(agent_runs.c.cancel_requested).where(agent_runs.c.id == run_id)
    ).first()
    return bool(row[0]) if row is not None else False


def list_running_runs(conn: Connection, worker_id: str | None = None) -> list[dict]:
    """Runs currently ``running`` — all of them, or one worker's (the reaper's sweep)."""
    stmt = select(agent_runs).where(agent_runs.c.status == "running")
    if worker_id is not None:
        stmt = stmt.where(agent_runs.c.worker_id == worker_id)
    rows = conn.execute(stmt.order_by(agent_runs.c.id)).all()
    return [dict(r._mapping) for r in rows]


def get_latest_run(conn: Connection, agent_id: int) -> dict | None:
    row = conn.execute(
        select(agent_runs)
        .where(agent_runs.c.agent_id == agent_id)
        .order_by(agent_runs.c.id.desc())
        .limit(1)
    ).first()
    return _row_to_dict(row)


def set_agent_session(
    conn: Connection, agent_id: int, session_id: str, worker_id: str
) -> None:
    """Record the claude session UUID + supervising worker on the agent row."""
    conn.execute(
        agents.update()
        .where(agents.c.id == agent_id)
        .values(session_id=session_id, worker_id=worker_id)
    )


def insert_agent_event(
    conn: Connection,
    agent_id: int,
    run_id: int,
    seq: int,
    type: str,
    payload: dict | None = None,
    session_id: str | None = None,
) -> int:
    result = conn.execute(
        agent_events.insert().values(
            agent_id=agent_id,
            run_id=run_id,
            session_id=session_id,
            seq=seq,
            type=type,
            payload=payload,
            created_at=_now(),
        )
    )
    return result.inserted_primary_key[0]


def list_agent_events(
    conn: Connection, agent_id: int, after_id: int = 0, limit: int = 200
) -> list[dict]:
    """Events for an agent in insertion order, cursor-paged by row id (the UI polls with
    ``after_id`` = the last id it has, so each poll returns only what's new)."""
    rows = conn.execute(
        select(agent_events)
        .where(agent_events.c.agent_id == agent_id, agent_events.c.id > after_id)
        .order_by(agent_events.c.id.asc())
        .limit(limit)
    ).all()
    return [dict(r._mapping) for r in rows]


def upsert_session_archive(
    conn: Connection, agent_id: int, session_id: str, archive: bytes
) -> None:
    """Store (replace) the agent's latest claude session archive."""
    now = _now()
    result = conn.execute(
        session_archives.update()
        .where(session_archives.c.agent_id == agent_id)
        .values(session_id=session_id, archive=archive, bytes=len(archive), updated_at=now)
    )
    if result.rowcount == 0:
        conn.execute(
            session_archives.insert().values(
                agent_id=agent_id, session_id=session_id, archive=archive,
                bytes=len(archive), updated_at=now,
            )
        )


def get_session_archive(conn: Connection, agent_id: int) -> dict | None:
    row = conn.execute(
        select(session_archives).where(session_archives.c.agent_id == agent_id)
    ).first()
    return _row_to_dict(row)


def upsert_runtime_secret(conn: Connection, key: str, value_enc: str) -> None:
    """Store an encrypted control-plane secret (the caller encrypts via secretstore)."""
    now = _now()
    result = conn.execute(
        runtime_secrets.update()
        .where(runtime_secrets.c.key == key)
        .values(value_enc=value_enc, updated_at=now)
    )
    if result.rowcount == 0:
        conn.execute(
            runtime_secrets.insert().values(key=key, value_enc=value_enc, updated_at=now)
        )


def get_runtime_secret(conn: Connection, key: str) -> dict | None:
    row = conn.execute(select(runtime_secrets).where(runtime_secrets.c.key == key)).first()
    return _row_to_dict(row)


# --------------------------------------------------- claude management (web-managed)


def list_claude_skills(conn: Connection, enabled_only: bool = False) -> list[dict]:
    stmt = select(claude_skills)
    if enabled_only:
        stmt = stmt.where(claude_skills.c.enabled.is_(True))
    rows = conn.execute(stmt.order_by(claude_skills.c.name)).all()
    return [dict(r._mapping) for r in rows]


def get_claude_skill(conn: Connection, skill_id: int) -> dict | None:
    row = conn.execute(select(claude_skills).where(claude_skills.c.id == skill_id)).first()
    return _row_to_dict(row)


def get_claude_skill_by_name(conn: Connection, name: str) -> dict | None:
    row = conn.execute(select(claude_skills).where(claude_skills.c.name == name)).first()
    return _row_to_dict(row)


def create_claude_skill(
    conn: Connection,
    name: str,
    content: str,
    description: str | None = None,
    enabled: bool = True,
) -> dict:
    now = _now()
    result = conn.execute(
        claude_skills.insert().values(
            name=name,
            description=description,
            content=content,
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )
    )
    return get_claude_skill(conn, result.inserted_primary_key[0])


def update_claude_skill(conn: Connection, skill_id: int, **fields: Any) -> dict | None:
    allowed = {"name", "description", "content", "enabled"}
    values = {k: v for k, v in fields.items() if k in allowed}
    if values:
        values["updated_at"] = _now()
        conn.execute(
            claude_skills.update().where(claude_skills.c.id == skill_id).values(**values)
        )
    return get_claude_skill(conn, skill_id)


def delete_claude_skill(conn: Connection, skill_id: int) -> bool:
    # Explicit dependent delete: SQLite only honors ON DELETE CASCADE with foreign_keys
    # pragma on, so don't rely on it.
    conn.execute(claude_skill_files.delete().where(claude_skill_files.c.skill_id == skill_id))
    result = conn.execute(claude_skills.delete().where(claude_skills.c.id == skill_id))
    return result.rowcount > 0


def list_claude_skill_files(conn: Connection, skill_id: int) -> list[dict]:
    rows = conn.execute(
        select(claude_skill_files)
        .where(claude_skill_files.c.skill_id == skill_id)
        .order_by(claude_skill_files.c.path)
    ).all()
    return [dict(r._mapping) for r in rows]


def set_claude_skill_files(conn: Connection, skill_id: int, files: dict[str, str]) -> None:
    """Replace a skill's auxiliary file set wholesale (the importer's write shape)."""
    conn.execute(claude_skill_files.delete().where(claude_skill_files.c.skill_id == skill_id))
    for path, content in sorted(files.items()):
        conn.execute(
            claude_skill_files.insert().values(skill_id=skill_id, path=path, content=content)
        )


def list_claude_connectors(conn: Connection, enabled_only: bool = False) -> list[dict]:
    stmt = select(claude_connectors)
    if enabled_only:
        stmt = stmt.where(claude_connectors.c.enabled.is_(True))
    rows = conn.execute(stmt.order_by(claude_connectors.c.name)).all()
    return [dict(r._mapping) for r in rows]


def get_claude_connector(conn: Connection, connector_id: int) -> dict | None:
    row = conn.execute(
        select(claude_connectors).where(claude_connectors.c.id == connector_id)
    ).first()
    return _row_to_dict(row)


def get_claude_connector_by_name(conn: Connection, name: str) -> dict | None:
    row = conn.execute(
        select(claude_connectors).where(claude_connectors.c.name == name)
    ).first()
    return _row_to_dict(row)


def create_claude_connector(
    conn: Connection,
    name: str,
    transport: str,
    command: str | None = None,
    args: list | None = None,
    env: dict | None = None,
    url: str | None = None,
    headers: dict | None = None,
    enabled: bool = True,
) -> dict:
    result = conn.execute(
        claude_connectors.insert().values(
            name=name,
            transport=transport,
            command=command,
            args=args,
            env=env,
            url=url,
            headers=headers,
            enabled=enabled,
            created_at=_now(),
        )
    )
    return get_claude_connector(conn, result.inserted_primary_key[0])


def update_claude_connector(conn: Connection, connector_id: int, **fields: Any) -> dict | None:
    allowed = {"name", "transport", "command", "args", "env", "url", "headers", "enabled"}
    values = {k: v for k, v in fields.items() if k in allowed}
    if values:
        conn.execute(
            claude_connectors.update()
            .where(claude_connectors.c.id == connector_id)
            .values(**values)
        )
    return get_claude_connector(conn, connector_id)


def delete_claude_connector(conn: Connection, connector_id: int) -> bool:
    result = conn.execute(
        claude_connectors.delete().where(claude_connectors.c.id == connector_id)
    )
    return result.rowcount > 0


def list_claude_plugins(conn: Connection, enabled_only: bool = False) -> list[dict]:
    stmt = select(claude_plugins)
    if enabled_only:
        stmt = stmt.where(claude_plugins.c.enabled.is_(True))
    rows = conn.execute(
        stmt.order_by(claude_plugins.c.marketplace, claude_plugins.c.name)
    ).all()
    return [dict(r._mapping) for r in rows]


def get_claude_plugin(conn: Connection, plugin_id: int) -> dict | None:
    row = conn.execute(select(claude_plugins).where(claude_plugins.c.id == plugin_id)).first()
    return _row_to_dict(row)


def get_claude_plugin_by_key(conn: Connection, name: str, marketplace: str) -> dict | None:
    row = conn.execute(
        select(claude_plugins).where(
            claude_plugins.c.name == name, claude_plugins.c.marketplace == marketplace
        )
    ).first()
    return _row_to_dict(row)


def create_claude_plugin(
    conn: Connection,
    name: str,
    marketplace: str,
    marketplace_repo: str,
    enabled: bool = True,
) -> dict:
    result = conn.execute(
        claude_plugins.insert().values(
            name=name,
            marketplace=marketplace,
            marketplace_repo=marketplace_repo,
            enabled=enabled,
            created_at=_now(),
        )
    )
    return get_claude_plugin(conn, result.inserted_primary_key[0])


def update_claude_plugin(conn: Connection, plugin_id: int, **fields: Any) -> dict | None:
    allowed = {"name", "marketplace", "marketplace_repo", "enabled"}
    values = {k: v for k, v in fields.items() if k in allowed}
    if values:
        conn.execute(
            claude_plugins.update().where(claude_plugins.c.id == plugin_id).values(**values)
        )
    return get_claude_plugin(conn, plugin_id)


def delete_claude_plugin(conn: Connection, plugin_id: int) -> bool:
    result = conn.execute(claude_plugins.delete().where(claude_plugins.c.id == plugin_id))
    return result.rowcount > 0


def get_claude_config(conn: Connection, key: str) -> Any | None:
    """The stored JSON value for a claude_config key, or None when unset."""
    row = conn.execute(select(claude_config).where(claude_config.c.key == key)).first()
    return row._mapping["value"] if row is not None else None


def set_claude_config(conn: Connection, key: str, value: Any) -> None:
    now = _now()
    result = conn.execute(
        claude_config.update().where(claude_config.c.key == key).values(value=value, updated_at=now)
    )
    if result.rowcount == 0:
        conn.execute(claude_config.insert().values(key=key, value=value, updated_at=now))


def get_latest_claimed_command(conn: Connection, type: str) -> dict | None:
    """The most recent command of a type that some worker has claimed (running or
    finished). Login pinning reads login_start's ``claimed_by`` to route login_submit to
    the same worker container — including while the login_start is still in flight."""
    row = conn.execute(
        select(commands)
        .where(commands.c.type == type, commands.c.claimed_by.is_not(None))
        .order_by(commands.c.id.desc())
        .limit(1)
    ).first()
    return _row_to_dict(row)
