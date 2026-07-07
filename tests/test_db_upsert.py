"""The highest-value DB test: the checkmark upsert overwrites in place (ON CONFLICT DO
UPDATE), keeping a single row with preserved identity — never delete+reinsert.
"""

from __future__ import annotations

from sqlalchemy import func, select

from handler.db import repository as repo
from handler.db.tables import checkmarks


def _seed_agent(conn):
    repo.create_project(conn, "p", "/tmp/p")
    return repo.create_agent(conn, "p", "a", "/tmp/p/a")


def test_upsert_overwrites_single_row(conn):
    agent = _seed_agent(conn)

    repo.upsert_checkmark_row(
        conn,
        agent["id"],
        status="working",
        where_it_stopped="first stop",
        tests_status="unknown",
    )
    repo.upsert_checkmark_row(
        conn,
        agent["id"],
        status="done",
        where_it_stopped="second stop",
        tests_status="pass",
    )

    count = conn.execute(select(func.count()).select_from(checkmarks)).scalar_one()
    assert count == 1

    row = repo.get_checkmark(conn, agent["id"])
    assert row["status"] == "done"
    assert row["where_it_stopped"] == "second stop"
    assert row["tests_status"] == "pass"
    assert row["agent_id"] == agent["id"]


def test_upsert_only_touches_supplied_columns_via_defaults(conn):
    agent = _seed_agent(conn)
    repo.upsert_checkmark_row(conn, agent["id"], status="working")
    row = repo.get_checkmark(conn, agent["id"])
    # Unsupplied gate columns fall back to their schema defaults.
    assert row["tests_status"] == "unknown"
    assert row["build_status"] == "unknown"
