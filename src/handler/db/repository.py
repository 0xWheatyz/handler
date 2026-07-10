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
    agents,
    approvals,
    checkmarks,
    commands,
    forge_hosts,
    log_entries,
    projects,
    shared_context,
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


def delete_project(conn: Connection, project_id: str) -> bool:
    result = conn.execute(projects.delete().where(projects.c.id == project_id))
    return result.rowcount > 0


def delete_agent(conn: Connection, project_id: str, name: str) -> bool:
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
) -> dict:
    """Insert a ``queued`` control command for the worker to pick up. Returns the row."""
    result = conn.execute(
        commands.insert().values(
            project_id=project_id,
            agent_name=agent_name,
            type=type,
            payload=payload,
            status="queued",
            requested_by=requested_by,
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


def claim_next_command(conn: Connection, worker_id: str) -> dict | None:
    """Atomically claim the oldest queued command, flipping it to ``running``.

    Postgres uses ``FOR UPDATE SKIP LOCKED`` so multiple workers never grab the same row;
    on SQLite (single writer per transaction) the guarded ``WHERE status='queued'`` update
    plus a rowcount check is enough. Returns the claimed row, or ``None`` when the queue is
    empty or another worker won the race.
    """
    sel = (
        select(commands.c.id)
        .where(commands.c.status == "queued")
        .order_by(commands.c.id.asc())
        .limit(1)
    )
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
) -> dict:
    conn.execute(
        forge_hosts.insert().values(
            hostname=hostname,
            forge_type=forge_type,
            token_env_var=token_env_var,
            base_url=base_url,
            created_at=_now(),
        )
    )
    return get_host(conn, hostname)


def update_host(conn: Connection, hostname: str, **fields: Any) -> dict | None:
    allowed = {"forge_type", "token_env_var", "base_url"}
    values = {k: v for k, v in fields.items() if k in allowed}
    if values:
        conn.execute(
            forge_hosts.update().where(forge_hosts.c.hostname == hostname).values(**values)
        )
    return get_host(conn, hostname)


def delete_host(conn: Connection, hostname: str) -> bool:
    result = conn.execute(forge_hosts.delete().where(forge_hosts.c.hostname == hostname))
    return result.rowcount > 0
