"""Per-user separation: users see shared resources plus their own — never each
other's — across projects, agents, schedules, memory, activity, and the Claude page
resources; the control layer applies only the owner's rows at launch."""

from __future__ import annotations

import pytest


@pytest.fixture
def users(client):
    """Three actors: an admin, and two regular users (alice, bob)."""
    r = client.post("/auth/setup", json={"email": "admin@x.co", "password": "admin-pass-1"})
    admin = {"Authorization": f"Bearer {r.json()['token']}"}
    out = {"admin": admin, "admin_user": r.json()["user"]}
    for name in ("alice", "bob"):
        invite = client.post(
            "/auth/users", json={"email": f"{name}@x.co"}, headers=admin
        ).json()
        token = invite["invite_url"].split("token=")[1]
        r = client.post("/auth/reset", json={"token": token, "password": f"{name}-pass-1"})
        out[name] = {"Authorization": f"Bearer {r.json()['token']}"}
        out[f"{name}_user"] = r.json()["user"]
    return out


def _mkproject(client, headers, pid):
    r = client.post("/projects", json={"id": pid, "root_dir": f"/tmp/{pid}"}, headers=headers)
    assert r.status_code == 201
    return r.json()


# ---- projects --------------------------------------------------------------------------


def test_projects_are_invisible_across_users(client, users):
    _mkproject(client, users["alice"], "alices")
    _mkproject(client, users["bob"], "bobs")

    assert [p["id"] for p in client.get("/projects", headers=users["alice"]).json()] == ["alices"]
    assert [p["id"] for p in client.get("/projects", headers=users["bob"]).json()] == ["bobs"]
    # Existence is not leaked: someone else's project 404s, as do its nested routes.
    assert client.get("/projects/bobs", headers=users["alice"]).status_code == 404
    assert client.get("/projects/bobs/agents", headers=users["alice"]).status_code == 404
    assert client.delete("/projects/bobs", headers=users["alice"]).status_code == 404
    # Admin sees and can manage everything.
    assert {p["id"] for p in client.get("/projects", headers=users["admin"]).json()} == {
        "alices", "bobs",
    }


def test_shared_projects_visible_but_admin_managed(client, users, env):
    token_headers = {"Authorization": f"Bearer {env['token']}"}
    _mkproject(client, token_headers, "sharedproj")  # env token => shared (owner NULL)

    assert client.get("/projects/sharedproj", headers=users["alice"]).status_code == 200
    # Viewing yes; mutating no — shared rows are admin-managed.
    r = client.patch(
        "/projects/sharedproj", json={"root_dir": "/tmp/x"}, headers=users["alice"]
    )
    assert r.status_code == 403
    assert client.patch(
        "/projects/sharedproj", json={"root_dir": "/tmp/x"}, headers=users["admin"]
    ).status_code == 200


def test_owner_operates_own_project_without_admin(client, users, fake_launch, tmp_path):
    """A regular user drives the full lifecycle on their own project (spawn needs a
    worker; here we only prove the API-side gates: enqueue allowed, 404 for others)."""
    _mkproject(client, users["alice"], "alices")
    r = client.post(
        "/projects/alices/agents/spawn",
        json={"name": "a1", "task": "do the thing"},
        headers=users["alice"],
    )
    assert r.status_code == 202
    assert r.json()["requested_by"].startswith("user:")
    # Bob can't even see the project, let alone spawn into it.
    r = client.post(
        "/projects/alices/agents/spawn",
        json={"name": "b1", "task": "sneaky"},
        headers=users["bob"],
    )
    assert r.status_code == 404


def test_admin_can_reassign_owner(client, users):
    _mkproject(client, users["alice"], "alices")
    bob_id = users["bob_user"]["id"]
    r = client.patch(
        "/projects/alices", json={"owner_user_id": bob_id}, headers=users["admin"]
    )
    assert r.status_code == 200 and r.json()["owner_user_id"] == bob_id
    assert client.get("/projects/alices", headers=users["alice"]).status_code == 404
    assert client.get("/projects/alices", headers=users["bob"]).status_code == 200
    # Owners themselves cannot hand projects around.
    r = client.patch(
        "/projects/alices", json={"owner_user_id": None}, headers=users["bob"]
    )
    assert r.status_code == 403


# ---- claude page resources (skills / connectors / plugins / models) --------------------


def test_skills_are_separated_and_shared_rows_common(client, users, env):
    token_headers = {"Authorization": f"Bearer {env['token']}"}
    mk = lambda h, name: client.post(  # noqa: E731
        "/claude/skills", json={"name": name, "content": "# x"}, headers=h
    )
    assert mk(token_headers, "shared-skill").status_code == 201
    alice_skill = mk(users["alice"], "alice-skill")
    assert alice_skill.status_code == 201
    assert alice_skill.json()["owner_user_id"] == users["alice_user"]["id"]
    assert mk(users["bob"], "bob-skill").status_code == 201

    names = lambda h: {s["name"] for s in client.get("/claude/skills", headers=h).json()}  # noqa: E731
    assert names(users["alice"]) == {"shared-skill", "alice-skill"}
    assert names(users["bob"]) == {"shared-skill", "bob-skill"}
    assert names(users["admin"]) == {"shared-skill", "alice-skill", "bob-skill"}

    # Cross-user mutation 404s (invisible); shared mutation 403s for non-admins.
    alice_id = alice_skill.json()["id"]
    assert client.delete(f"/claude/skills/{alice_id}", headers=users["bob"]).status_code == 404
    shared_id = next(
        s["id"] for s in client.get("/claude/skills", headers=users["admin"]).json()
        if s["name"] == "shared-skill"
    )
    assert client.patch(
        f"/claude/skills/{shared_id}", json={"enabled": False}, headers=users["alice"]
    ).status_code == 403
    assert client.delete(f"/claude/skills/{alice_id}", headers=users["alice"]).status_code == 200


def test_connectors_plugins_models_follow_same_rules(client, users):
    a, b = users["alice"], users["bob"]
    r = client.post(
        "/claude/connectors",
        json={"name": "alice-mcp", "transport": "http", "url": "https://a.example/mcp"},
        headers=a,
    )
    assert r.status_code == 201
    r = client.post(
        "/claude/plugins",
        json={"name": "alice-plug", "marketplace": "mp", "marketplace_repo": "o/r"},
        headers=a,
    )
    assert r.status_code == 201
    r = client.post(
        "/claude/models",
        json={"name": "alice-model", "base_url": "http://localhost:4000", "model": "m"},
        headers=a,
    )
    assert r.status_code == 201
    model_id = r.json()["id"]

    assert client.get("/claude/connectors", headers=b).json() == []
    assert client.get("/claude/plugins", headers=b).json() == []
    assert client.get("/claude/models", headers=b).json() == []

    # Bob can't spawn or schedule onto Alice's private model backend.
    _mkproject(client, b, "bobs")
    r = client.post(
        "/projects/bobs/agents/spawn",
        json={"name": "b1", "task": "t", "model_id": model_id},
        headers=b,
    )
    assert r.status_code == 400 and "not found" in r.json()["detail"]
    r = client.post(
        "/projects/bobs/schedules",
        json={"name_prefix": "s", "task": "t", "interval_seconds": 3600, "model_id": model_id},
        headers=b,
    )
    assert r.status_code == 400


# ---- schedules, activity, memory -------------------------------------------------------


def test_schedules_follow_project_visibility(client, users):
    _mkproject(client, users["alice"], "alices")
    r = client.post(
        "/projects/alices/schedules",
        json={"name_prefix": "nightly", "task": "t", "interval_seconds": 3600},
        headers=users["alice"],
    )
    assert r.status_code == 201
    sid = r.json()["id"]

    assert client.get("/schedules", headers=users["bob"]).json() == []
    assert client.get("/projects/alices/schedules", headers=users["bob"]).status_code == 404
    assert client.patch(
        f"/schedules/{sid}", json={"enabled": False}, headers=users["bob"]
    ).status_code == 404
    assert len(client.get("/schedules", headers=users["admin"]).json()) == 1
    assert client.delete(f"/schedules/{sid}", headers=users["alice"]).status_code == 200


def test_activity_feed_is_scoped(client, users):
    _mkproject(client, users["alice"], "alices")
    r = client.post(
        "/projects/alices/agents/spawn",
        json={"name": "a1", "task": "t"},
        headers=users["alice"],
    )
    cmd_id = r.json()["id"]

    assert client.get("/commands", headers=users["bob"]).json() == []
    assert client.get(f"/commands/{cmd_id}", headers=users["bob"]).status_code == 404
    assert client.get(f"/commands/{cmd_id}", headers=users["alice"]).status_code == 200
    assert len(client.get("/commands", headers=users["admin"]).json()) == 1


def test_memory_notes_follow_project_visibility(client, users):
    _mkproject(client, users["alice"], "alices")
    r = client.post(
        "/memory/notes",
        json={"title": "alice fact", "body": "b", "kind": "fact", "project_id": "alices"},
        headers=users["alice"],
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # Global notes reach every user's agents, so only admins write them.
    r = client.post(
        "/memory/notes", json={"title": "global", "body": "b", "kind": "fact"},
        headers=users["alice"],
    )
    assert r.status_code == 403
    assert client.post(
        "/memory/notes", json={"title": "global", "body": "b", "kind": "fact"},
        headers=users["admin"],
    ).status_code == 201

    bob_titles = {n["title"] for n in client.get("/memory/notes", headers=users["bob"]).json()}
    assert bob_titles == {"global"}  # global visible, alice's project note not
    assert client.get(f"/memory/notes/{note_id}", headers=users["bob"]).status_code == 404
    graph = client.get("/memory/graph", headers=users["bob"]).json()
    assert {n["title"] for n in graph["notes"]} == {"global"}


# ---- control layer: what a launch materializes -----------------------------------------


def test_launch_applies_only_owner_and_shared_rows(client, users, conn, tmp_path):
    """claude_gen.apply for a project owned by alice syncs shared + alice's skills and
    connectors — never bob's."""
    from handler.control import claude_gen
    from handler.db import repository as repo

    alice_id = users["alice_user"]["id"]
    bob_id = users["bob_user"]["id"]
    repo.create_claude_skill(conn, "shared-skill", "# s")
    repo.create_claude_skill(conn, "alice-skill", "# a", owner_user_id=alice_id)
    repo.create_claude_skill(conn, "bob-skill", "# b", owner_user_id=bob_id)
    repo.create_claude_connector(
        conn, "alice-mcp", "http", url="https://a.example/mcp", owner_user_id=alice_id
    )
    repo.create_claude_connector(
        conn, "bob-mcp", "http", url="https://b.example/mcp", owner_user_id=bob_id
    )

    workdir = tmp_path / "wd"
    workdir.mkdir()
    summary = claude_gen.apply(str(workdir), conn=conn, visible_to=alice_id)
    assert summary["skills_written"] == 2  # shared + alice's

    import json
    import os

    mcp = json.load(open(claude_gen.mcp_config_path(str(workdir))))
    assert "alice-mcp" in mcp["mcpServers"] and "bob-mcp" not in mcp["mcpServers"]
    skills_root = os.path.expanduser("~/.claude/skills")
    synced = set(os.listdir(skills_root))
    assert {"shared-skill", "alice-skill"} <= synced and "bob-skill" not in synced

    # A shared/legacy project (owner None) gets shared rows only.
    summary = claude_gen.apply(str(workdir), conn=conn, visible_to=None)
    assert summary["skills_written"] == 1
    synced = set(os.listdir(skills_root))
    assert "alice-skill" not in synced and "shared-skill" in synced
