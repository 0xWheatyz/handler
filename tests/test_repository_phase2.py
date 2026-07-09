"""Phase 2 DAL: agent role, approvals, and CI backfill helpers."""

from __future__ import annotations

from handler.db import repository as repo


def test_agent_role_is_stored(conn):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "senior", "/tmp/p/senior", role="senior")
    assert a["role"] == "senior"
    assert repo.get_agent_by_id(conn, a["id"])["role"] == "senior"


def test_approval_record_and_latest(conn):
    repo.create_project(conn, "p", "/tmp/p")
    junior = repo.create_agent(conn, "p", "junior", "/tmp/p/j", role="junior")
    senior = repo.create_agent(conn, "p", "senior", "/tmp/p/s", role="senior")

    assert repo.get_latest_approval(conn, "p", "feat/x") is None

    repo.record_approval(conn, "p", "feat/x", "rejected", junior["id"], note="nit")
    latest = repo.record_approval(conn, "p", "feat/x", "approved", senior["id"], pr_ref="7")
    got = repo.get_latest_approval(conn, "p", "feat/x")
    # Latest wins (by insertion order).
    assert got["id"] == latest["id"]
    assert got["status"] == "approved"
    assert got["approved_by_agent_id"] == senior["id"]
    assert got["pr_ref"] == "7"


def test_approval_scoped_by_project_and_branch(conn):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "s", "/tmp/p/s")
    repo.record_approval(conn, "p", "feat/x", "approved", a["id"])
    assert repo.get_latest_approval(conn, "p", "feat/other") is None


def test_pending_ci_entries_and_backfill(conn):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "a", "/tmp/p/a")
    # A push-recording entry (pending) and a normal entry (not_applicable).
    pending_id = repo.insert_log_entry(
        conn, a["id"], status="working", push_sha="deadbeef", ci_status="pending"
    )
    repo.insert_log_entry(conn, a["id"], status="working", summary="no push")

    entries = repo.get_pending_ci_entries(conn)
    assert [e["id"] for e in entries] == [pending_id]
    assert entries[0]["push_sha"] == "deadbeef"
    assert entries[0]["project_id"] == "p"
    assert entries[0]["working_dir"] == "/tmp/p/a"

    assert repo.update_ci_status(conn, pending_id, "pass") is True
    # No longer pending once resolved.
    assert repo.get_pending_ci_entries(conn) == []
    assert repo.get_log(conn, a["id"])[-1]["ci_status"] in ("pass", "not_applicable")


def test_pending_ci_entries_scoped_to_project(conn):
    repo.create_project(conn, "p1", "/tmp/p1")
    repo.create_project(conn, "p2", "/tmp/p2")
    a1 = repo.create_agent(conn, "p1", "a", "/tmp/p1/a")
    a2 = repo.create_agent(conn, "p2", "a", "/tmp/p2/a")
    repo.insert_log_entry(conn, a1["id"], status="working", push_sha="s1", ci_status="pending")
    repo.insert_log_entry(conn, a2["id"], status="working", push_sha="s2", ci_status="pending")
    assert [e["project_id"] for e in repo.get_pending_ci_entries(conn, project_id="p1")] == ["p1"]
