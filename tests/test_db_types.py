"""Portable types round-trip correctly on SQLite (aware datetimes, JSON lists)."""

from __future__ import annotations

from datetime import UTC, datetime

from handler.db import repository as repo


def _seed_agent(conn):
    repo.create_project(conn, "p", "/tmp/p")
    return repo.create_agent(conn, "p", "a", "/tmp/p/a")


def test_timestamp_roundtrips_as_utc_aware(conn):
    agent = _seed_agent(conn)
    ts = datetime(2026, 7, 7, 12, 30, tzinfo=UTC)
    repo.upsert_checkmark_row(conn, agent["id"], checkpoint_at=ts, status="working")
    row = repo.get_checkmark(conn, agent["id"])
    assert row["checkpoint_at"] == ts
    assert row["checkpoint_at"].tzinfo is not None


def test_naive_timestamp_is_normalized_to_utc(conn):
    agent = _seed_agent(conn)
    naive = datetime(2026, 7, 7, 12, 30)  # no tzinfo
    repo.upsert_checkmark_row(conn, agent["id"], checkpoint_at=naive, status="working")
    row = repo.get_checkmark(conn, agent["id"])
    assert row["checkpoint_at"] == naive.replace(tzinfo=UTC)


def test_json_list_roundtrips(conn):
    agent = _seed_agent(conn)
    steps = ["write tests", "wire the poller", "document the token flow"]
    repo.upsert_checkmark_row(
        conn, agent["id"], status="working", next_steps=steps
    )
    row = repo.get_checkmark(conn, agent["id"])
    assert row["next_steps"] == steps
