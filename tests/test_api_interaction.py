"""Answer + resume routes, including the mocked control seam."""

from __future__ import annotations

from handler.control import spawn
from handler.db import repository as repo
from handler.db.engine import get_engine


def _seed_agent_with_question(env):
    """Seed a project + agent + an open question directly in the DB."""
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", "/tmp/proj")
        a = repo.create_agent(conn, "proj", "api", "/tmp/proj/api", status="paused_for_input")
        log_id = repo.insert_log_entry(
            conn, a["id"], status="paused_for_input", question="Which DB?"
        )
    return a, log_id


def test_answer_backfills_latest_open_question(client, auth, env):
    _seed_agent_with_question(env)
    r = client.post(
        "/projects/proj/agents/api/answer",
        json={"answer": "Postgres"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["answered"] is True

    with get_engine().begin() as conn:
        a = repo.get_agent_by_name(conn, "proj", "api")
        assert repo.get_log(conn, a["id"])[0]["answer"] == "Postgres"


def test_answer_with_no_open_question_is_404(client, auth, env):
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", "/tmp/proj")
        repo.create_agent(conn, "proj", "api", "/tmp/proj/api")
    r = client.post(
        "/projects/proj/agents/api/answer", json={"answer": "x"}, headers=auth
    )
    assert r.status_code == 404


def test_resume_calls_control_seam(client, auth, env, monkeypatch):
    _seed_agent_with_question(env)
    client.post(
        "/projects/proj/agents/api/answer", json={"answer": "Postgres"}, headers=auth
    )

    calls = []

    def fake_resume(agent, answer):
        calls.append((agent["name"], answer))
        return True, "delivered"

    monkeypatch.setattr(spawn, "resume", fake_resume)

    r = client.post("/projects/proj/agents/api/resume", json={}, headers=auth)
    assert r.status_code == 200
    assert r.json()["resumed"] is True
    assert calls == [("api", "Postgres")]

    with get_engine().begin() as conn:
        a = repo.get_agent_by_name(conn, "proj", "api")
        assert a["status"] == "working"


def test_resume_without_answer_is_400(client, auth, env, monkeypatch):
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", "/tmp/proj")
        repo.create_agent(conn, "proj", "api", "/tmp/proj/api")
    monkeypatch.setattr(spawn, "resume", lambda a, ans: (True, "x"))
    r = client.post("/projects/proj/agents/api/resume", json={}, headers=auth)
    assert r.status_code == 400
