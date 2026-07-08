"""The one place dialect branching lives: the checkmark upsert.

``checkmarks`` is a literal upsert keyed by ``agent_id`` — "the small file that gets
overwritten," as a row. We use native ``INSERT ... ON CONFLICT DO UPDATE`` on *both*
dialects (SQLite >= 3.24, from 2018; Python 3.11 bundles far newer). Deliberately not
``INSERT OR REPLACE``: that deletes and reinserts the row, firing FK cascades and
losing row identity.
"""

from __future__ import annotations

from sqlalchemy import Connection
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .tables import checkmarks


def upsert_checkmark(conn: Connection, values: dict) -> None:
    """Insert or overwrite the checkmark for ``values['agent_id']``.

    Every non-PK column present in ``values`` is overwritten on conflict, so a
    checkpoint fully replaces the prior small-state record.
    """
    if "agent_id" not in values:
        raise ValueError("upsert_checkmark requires 'agent_id'")

    dialect = conn.dialect.name
    if dialect == "postgresql":
        stmt = pg_insert(checkmarks).values(**values)
    elif dialect == "sqlite":
        stmt = sqlite_insert(checkmarks).values(**values)
    else:  # pragma: no cover - only two backends are supported
        raise RuntimeError(f"unsupported dialect for upsert: {dialect}")

    update_cols = {k: stmt.excluded[k] for k in values if k != "agent_id"}
    stmt = stmt.on_conflict_do_update(index_elements=["agent_id"], set_=update_cols)
    conn.execute(stmt)
