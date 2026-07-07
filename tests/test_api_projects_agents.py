"""Project + agent routes, and project isolation (README 3.4)."""

from __future__ import annotations


def _mk_project(client, auth, pid="proj", root="/tmp/proj"):
    return client.post("/projects", json={"id": pid, "root_dir": root}, headers=auth)


def test_create_and_list_project(client, auth):
    r = _mk_project(client, auth)
    assert r.status_code == 201
    assert r.json()["id"] == "proj"
    listing = client.get("/projects", headers=auth).json()
    assert [p["id"] for p in listing] == ["proj"]


def test_duplicate_project_conflicts(client, auth):
    _mk_project(client, auth)
    assert _mk_project(client, auth).status_code == 409


def test_create_and_list_agent(client, auth):
    _mk_project(client, auth)
    r = client.post(
        "/projects/proj/agents",
        json={"name": "api", "working_dir": "/tmp/proj/api"},
        headers=auth,
    )
    assert r.status_code == 201
    agents = client.get("/projects/proj/agents", headers=auth).json()
    assert [a["name"] for a in agents] == ["api"]


def test_agent_under_missing_project_is_404(client, auth):
    r = client.get("/projects/ghost/agents", headers=auth)
    assert r.status_code == 404


def test_project_isolation_same_agent_name(client, auth):
    # Two projects can each have an agent named "api"; neither leaks into the other.
    _mk_project(client, auth, "a", "/tmp/a")
    _mk_project(client, auth, "b", "/tmp/b")
    client.post(
        "/projects/a/agents",
        json={"name": "api", "working_dir": "/tmp/a/api"},
        headers=auth,
    )
    a_agents = client.get("/projects/a/agents", headers=auth).json()
    b_agents = client.get("/projects/b/agents", headers=auth).json()
    assert [x["name"] for x in a_agents] == ["api"]
    assert b_agents == []
    # The agent is invisible under project b.
    assert client.get("/projects/b/agents/api/checkmark", headers=auth).status_code == 404


def test_checkmark_404_before_any_checkpoint(client, auth):
    _mk_project(client, auth)
    client.post(
        "/projects/proj/agents",
        json={"name": "api", "working_dir": "/tmp/proj/api"},
        headers=auth,
    )
    assert client.get("/projects/proj/agents/api/checkmark", headers=auth).status_code == 404
