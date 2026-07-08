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

from .tables import agents, checkmarks, log_entries, projects, shared_context
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
) -> dict:
    result = conn.execute(
        agents.insert().values(
            project_id=project_id,
            name=name,
            working_dir=working_dir,
            status=status,
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
