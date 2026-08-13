"""Built-in operator skills: seeding is idempotent and respects operator changes."""

from __future__ import annotations

from handler.builtin_skills import BUILTIN_SKILLS, seed_builtin_skills
from handler.db import repository as repo


def test_seed_creates_all_builtins(conn):
    created = seed_builtin_skills(conn)
    assert sorted(created) == sorted(name for name, _, _ in BUILTIN_SKILLS)

    rows = {s["name"]: s for s in repo.list_claude_skills(conn)}
    for name, description, body in BUILTIN_SKILLS:
        row = rows[name]
        assert row["enabled"] is True
        assert row["owner_user_id"] is None  # shared: visible to everyone
        assert row["description"] == description
        assert row["content"] == body


def test_seed_is_idempotent(conn):
    seed_builtin_skills(conn)
    assert seed_builtin_skills(conn) == []
    names = [s["name"] for s in repo.list_claude_skills(conn)]
    assert len(names) == len(set(names))


def test_seed_preserves_operator_edits_and_disables(conn):
    seed_builtin_skills(conn)
    row = repo.get_claude_skill_by_name(conn, "handler-gate-recovery")
    repo.update_claude_skill(conn, row["id"], content="operator version", enabled=False)

    assert seed_builtin_skills(conn) == []
    after = repo.get_claude_skill_by_name(conn, "handler-gate-recovery")
    assert after["content"] == "operator version"
    assert after["enabled"] is False


def test_seed_restores_deleted_builtin(conn):
    seed_builtin_skills(conn)
    row = repo.get_claude_skill_by_name(conn, "handler-secrets")
    repo.delete_claude_skill(conn, row["id"])

    assert seed_builtin_skills(conn) == ["handler-secrets"]
    assert repo.get_claude_skill_by_name(conn, "handler-secrets") is not None


def test_builtin_names_are_valid_slugs():
    # The API's skill-name pattern; content synced to workers relies on these being
    # safe directory names.
    import re

    slug = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    for name, description, body in BUILTIN_SKILLS:
        assert slug.match(name), name
        assert len(name) <= 64
        assert description.strip()
        assert body.strip()


def test_api_startup_seeds_builtins(env):
    # The lifespan hook fires when the app is entered as a context manager.
    from fastapi.testclient import TestClient

    from handler.api.app import create_app
    from handler.db.engine import get_engine

    with TestClient(create_app()):
        pass

    with get_engine().connect() as conn:
        names = {s["name"] for s in repo.list_claude_skills(conn)}
    assert {name for name, _, _ in BUILTIN_SKILLS} <= names
