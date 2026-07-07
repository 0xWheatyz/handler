"""DAL read/write functions and the answer backfill."""

from __future__ import annotations

from handler.db import repository as repo


def test_project_and_agent_crud(conn):
    repo.create_project(conn, "proj", "/tmp/proj", git_remote="git@x:proj.git")
    assert repo.get_project(conn, "proj")["root_dir"] == "/tmp/proj"
    assert [p["id"] for p in repo.list_projects(conn)] == ["proj"]

    a = repo.create_agent(conn, "proj", "api", "/tmp/proj/api")
    assert a["status"] == "working"
    assert repo.get_agent_by_name(conn, "proj", "api")["id"] == a["id"]
    assert repo.get_agent_by_name(conn, "proj", "missing") is None


def test_log_insert_and_answer_backfill(conn):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "a", "/tmp/p/a")

    log_id = repo.insert_log_entry(
        conn, a["id"], status="paused_for_input", question="Which DB?"
    )
    open_q = repo.get_latest_open_question(conn, a["id"])
    assert open_q["id"] == log_id

    assert repo.update_log_answer(conn, log_id, "Postgres") is True
    # Once answered, it is no longer an open question.
    assert repo.get_latest_open_question(conn, a["id"]) is None
    assert repo.get_log(conn, a["id"])[0]["answer"] == "Postgres"


def test_shared_context_upsert(conn):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "a", "/tmp/p/a")

    repo.set_shared_context(conn, "staging_url", "https://a", a["id"])
    assert repo.get_shared_context_key(conn, "staging_url")["value"] == "https://a"
    repo.set_shared_context(conn, "staging_url", "https://b", a["id"])
    assert repo.get_shared_context_key(conn, "staging_url")["value"] == "https://b"
    assert len(repo.get_shared_context(conn)) == 1


def test_shared_log_only_global(conn):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "a", "/tmp/p/a")
    repo.insert_log_entry(conn, a["id"], status="working", summary="private")
    repo.insert_log_entry(
        conn, a["id"], status="working", summary="shared", visibility="global"
    )
    shared = repo.get_shared_log(conn)
    assert [e["summary"] for e in shared] == ["shared"]
