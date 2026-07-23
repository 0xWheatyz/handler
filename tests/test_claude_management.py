"""The Claude management surface: /claude API CRUD + admin gating, the generation that
applies it (settings permissions/plugins, the --mcp-config file, user-level skills), and
the spawn integration that ties them together.

Spawns go through the ``fake_launch`` seam; the conftest ``env`` fixture points $HOME at
the per-test tmp dir, so skill syncs never touch a real ``~/.claude``.
"""

from __future__ import annotations

import json
import os
import shutil

import pytest

from handler.control import claude_gen, headless, settings_gen, skill_install, spawn, worker
from handler.db import repository as repo
from handler.db.engine import get_engine


@pytest.fixture
def lowpriv(env):
    """A valid bearer that is NOT the admin token (the shared-context write token)."""
    return {"Authorization": f"Bearer {env['shared_token']}"}


# --- repository ------------------------------------------------------------------------


def test_repository_skill_crud_and_config_kv(conn):
    skill = repo.create_claude_skill(conn, "deploy-notes", "# body", description="d")
    assert skill["enabled"] is True
    assert repo.get_claude_skill_by_name(conn, "deploy-notes")["id"] == skill["id"]

    updated = repo.update_claude_skill(conn, skill["id"], content="# new", enabled=False)
    assert updated["content"] == "# new" and updated["enabled"] is False
    assert repo.list_claude_skills(conn, enabled_only=True) == []
    assert len(repo.list_claude_skills(conn)) == 1

    assert repo.delete_claude_skill(conn, skill["id"]) is True
    assert repo.get_claude_skill(conn, skill["id"]) is None

    assert repo.get_claude_config(conn, "permissions") is None
    repo.set_claude_config(conn, "permissions", {"allow": ["Bash(npm *)"]})
    repo.set_claude_config(conn, "permissions", {"allow": ["Bash(go *)"]})  # upsert
    assert repo.get_claude_config(conn, "permissions") == {"allow": ["Bash(go *)"]}


# --- API CRUD + gating -----------------------------------------------------------------


def test_skill_api_crud(client, auth):
    r = client.post(
        "/claude/skills",
        json={"name": "deploy-notes", "description": "when deploying", "content": "# steps"},
        headers=auth,
    )
    assert r.status_code == 201
    sid = r.json()["id"]

    # Duplicate name refused.
    dup = client.post(
        "/claude/skills", json={"name": "deploy-notes", "content": "x"}, headers=auth
    )
    assert dup.status_code == 409

    # Unsafe names (path separators, dot-prefix) never become dirnames.
    bad = client.post(
        "/claude/skills", json={"name": "../escape", "content": "x"}, headers=auth
    )
    assert bad.status_code == 422

    patched = client.patch(f"/claude/skills/{sid}", json={"enabled": False}, headers=auth)
    assert patched.status_code == 200 and patched.json()["enabled"] is False

    assert client.get("/claude/skills", headers=auth).json()[0]["name"] == "deploy-notes"
    assert client.delete(f"/claude/skills/{sid}", headers=auth).status_code == 200
    assert client.get("/claude/skills", headers=auth).json() == []


def test_connector_api_crud_and_validation(client, auth):
    # stdio without a command is refused.
    bad = client.post(
        "/claude/connectors", json={"name": "gh", "transport": "stdio"}, headers=auth
    )
    assert bad.status_code == 422
    # http without an http(s) url is refused.
    bad = client.post(
        "/claude/connectors",
        json={"name": "gh", "transport": "http", "url": "ftp://x"},
        headers=auth,
    )
    assert bad.status_code == 422

    r = client.post(
        "/claude/connectors",
        json={
            "name": "github",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "tok"},
        },
        headers=auth,
    )
    assert r.status_code == 201
    cid = r.json()["id"]

    # A PATCH can't strand the row in an invalid pairing (http with no url).
    bad = client.patch(f"/claude/connectors/{cid}", json={"transport": "http"}, headers=auth)
    assert bad.status_code == 422

    ok = client.patch(
        f"/claude/connectors/{cid}",
        json={"transport": "http", "url": "https://mcp.example.com/mcp"},
        headers=auth,
    )
    assert ok.status_code == 200 and ok.json()["url"] == "https://mcp.example.com/mcp"

    assert client.delete(f"/claude/connectors/{cid}", headers=auth).status_code == 200


def test_plugin_api_crud(client, auth):
    r = client.post(
        "/claude/plugins",
        json={"name": "reviewer", "marketplace": "acme", "marketplace_repo": "acme/market"},
        headers=auth,
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    dup = client.post(
        "/claude/plugins",
        json={"name": "reviewer", "marketplace": "acme", "marketplace_repo": "acme/market"},
        headers=auth,
    )
    assert dup.status_code == 409

    bad = client.post(
        "/claude/plugins",
        json={"name": "x", "marketplace": "m", "marketplace_repo": "not a repo"},
        headers=auth,
    )
    assert bad.status_code == 422

    assert client.delete(f"/claude/plugins/{pid}", headers=auth).status_code == 200


def test_permissions_roundtrip_carries_baseline(client, auth):
    base = client.get("/claude/permissions", headers=auth).json()
    assert base["default_mode"] is None
    assert base["base_mode"] == "acceptEdits"
    assert "Bash(git *)" in base["base_allow"]

    r = client.put(
        "/claude/permissions",
        json={"default_mode": "plan", "allow": ["Bash(npm *)", "  "], "deny": ["WebFetch"]},
        headers=auth,
    )
    assert r.status_code == 200
    saved = client.get("/claude/permissions", headers=auth).json()
    assert saved["default_mode"] == "plan"
    assert saved["allow"] == ["Bash(npm *)"]  # blanks dropped
    assert saved["deny"] == ["WebFetch"]

    bad = client.put("/claude/permissions", json={"default_mode": "yolo"}, headers=auth)
    assert bad.status_code == 422


def test_claude_writes_need_admin(client, auth, lowpriv):
    # Reads pass with any valid bearer...
    assert client.get("/claude/skills", headers=lowpriv).status_code == 200
    assert client.get("/claude/permissions", headers=lowpriv).status_code == 200
    # ...writes need the admin token.
    r = client.post("/claude/skills", json={"name": "s", "content": "x"}, headers=lowpriv)
    assert r.status_code == 403
    assert client.put("/claude/permissions", json={}, headers=lowpriv).status_code == 403
    r = client.post(
        "/claude/connectors",
        json={"name": "c", "transport": "stdio", "command": "x"},
        headers=lowpriv,
    )
    assert r.status_code == 403


# --- generation ------------------------------------------------------------------------


def test_settings_merge_db_permissions_and_plugins(env):
    with get_engine().begin() as conn:
        repo.set_claude_config(
            conn,
            "permissions",
            {
                "default_mode": "plan",
                "allow": ["Bash(npm *)", "Bash(git *)"],  # git already in the baseline
                "deny": ["WebFetch"],
                "ask": ["Bash(rm *)"],
            },
        )
        repo.create_claude_plugin(conn, "reviewer", "acme", "acme/market")
        repo.create_claude_plugin(conn, "linter", "tools", "https://git.corp/m.git")
        repo.create_claude_plugin(conn, "off", "acme", "acme/market", enabled=False)
        settings = settings_gen.build_settings(conn)

    perms = settings["permissions"]
    assert perms["defaultMode"] == "plan"
    assert perms["allow"].count("Bash(git *)") == 1  # no duplicate from the merge
    assert "Bash(npm *)" in perms["allow"]
    assert perms["deny"] == ["WebFetch"]
    assert perms["ask"] == ["Bash(rm *)"]

    markets = settings["extraKnownMarketplaces"]
    assert markets["acme"] == {"source": {"source": "github", "repo": "acme/market"}}
    assert markets["tools"] == {"source": {"source": "git", "url": "https://git.corp/m.git"}}
    assert settings["enabledPlugins"] == {"reviewer@acme": True, "linter@tools": True}
    assert "hooks" in settings  # the hard gate is untouched


def test_mcp_config_written_and_removed(env, tmp_path):
    wd = str(tmp_path / "wd")
    connectors = [
        {
            "name": "github",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "server-github"],
            "env": {"GITHUB_TOKEN": "tok"},
        },
        {"name": "docs", "transport": "http", "url": "https://mcp.x/mcp", "headers": {"A": "b"}},
    ]
    path = claude_gen.write_mcp_config(wd, connectors)
    data = json.loads(open(path).read())
    assert data["mcpServers"]["github"] == {
        "command": "npx",
        "args": ["-y", "server-github"],
        "env": {"GITHUB_TOKEN": "tok"},
    }
    assert data["mcpServers"]["docs"] == {
        "type": "http",
        "url": "https://mcp.x/mcp",
        "headers": {"A": "b"},
    }
    # No connectors left => the previously generated file is removed.
    assert claude_gen.write_mcp_config(wd, []) is None
    assert not os.path.exists(path)


def test_skills_sync_and_managed_cleanup(env, tmp_path):
    home = str(tmp_path / "home")
    # A hand-installed skill (no marker) must survive every sync.
    manual = tmp_path / "home" / ".claude" / "skills" / "hand-made"
    manual.mkdir(parents=True)
    (manual / "SKILL.md").write_text("mine")

    written = claude_gen.sync_user_skills(
        [{"name": "deploy", "description": "when deploying", "content": "# steps"}], home=home
    )
    text = open(written[0]).read()
    assert text.startswith("---\nname: deploy\ndescription: when deploying\n---\n")
    assert "# steps" in text

    # The managed skill disappears when no longer enabled; the manual one stays.
    claude_gen.sync_user_skills([], home=home)
    assert not os.path.exists(os.path.dirname(written[0]))
    assert (manual / "SKILL.md").read_text() == "mine"


def test_argv_carries_mcp_config():
    argv = headless.build_spawn_argv("task", "/s.json", "sid", "/wd/.claude/mcp-servers.json")
    i = argv.index("--mcp-config")
    assert argv[i + 1] == "/wd/.claude/mcp-servers.json"
    assert "--mcp-config" not in headless.build_spawn_argv("task", "/s.json", "sid")
    argv = headless.build_resume_argv("sid", "answer", "/s.json", "/m.json")
    assert argv[argv.index("--mcp-config") + 1] == "/m.json"


# --- install from a marketplace prompt -------------------------------------------------


def _stage_skill(staging, name, front="---\nname: {n}\ndescription: fetched\n---\n", extra=None):
    d = staging / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(front.format(n=name) + "# fetched body\n")
    for rel, content in (extra or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)
    return d


def test_import_staged_creates_and_updates(conn, tmp_path):
    staging = tmp_path / "stage"
    _stage_skill(
        staging, "pdf-tools", extra={"references/usage.md": "how-to", "scripts/x.py": "print()"}
    )
    results = skill_install.import_staged(str(staging), conn)
    assert results == [
        {
            "name": "pdf-tools",
            "action": "created",
            "extra_files": ["references/usage.md", "scripts/x.py"],
        }
    ]
    row = repo.get_claude_skill_by_name(conn, "pdf-tools")
    assert row["description"] == "fetched" and "# fetched body" in row["content"]
    files = repo.list_claude_skill_files(conn, row["id"])
    assert [f["path"] for f in files] == ["references/usage.md", "scripts/x.py"]

    # Reinstall = update in place (same row, refreshed content + file set).
    shutil.rmtree(staging)
    _stage_skill(staging, "pdf-tools", extra={"references/v2.md": "new"})
    results = skill_install.import_staged(str(staging), conn)
    assert results[0]["action"] == "updated"
    again = repo.get_claude_skill_by_name(conn, "pdf-tools")
    assert again["id"] == row["id"]
    assert [f["path"] for f in repo.list_claude_skill_files(conn, again["id"])] == [
        "references/v2.md"
    ]


def test_import_staged_tolerates_messy_output(conn, tmp_path):
    staging = tmp_path / "stage"
    # No front-matter: name falls back to the dirname, description to the name.
    d = staging / "bare"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("just a body\n")
    # Binary sidecar files are skipped, not fatal.
    _stage_skill(staging, "with-bin", extra={"img.png": b"\x89PNG\x00\xff"})
    # A dir without SKILL.md (clone debris) is ignored.
    (staging / "debris").mkdir()
    (staging / "debris" / "README.md").write_text("not a skill")

    results = skill_install.import_staged(str(staging), conn)
    by_name = {r["name"]: r for r in results}
    assert set(by_name) == {"bare", "with-bin"}
    assert repo.get_claude_skill_by_name(conn, "bare")["description"] == "bare"
    assert by_name["with-bin"]["skipped_files"] == ["img.png (binary)"]
    assert repo.get_claude_skill_by_name(conn, "debris") is None


def test_skill_install_command_runs_wrapped_prompt(env, monkeypatch):
    """The worker command fakes the claude run: assert the pasted prompt travels inside
    the non-interactive wrapper, and the staged result lands as managed rows."""
    seen = {}

    def fake_run_claude(prompt, staging_dir, settings_path):
        seen["prompt"] = prompt
        assert "permissions" in json.load(open(settings_path))
        d = os.path.join(staging_dir, "deploy-helper")
        os.makedirs(d)
        with open(os.path.join(d, "SKILL.md"), "w") as fh:
            fh.write("---\nname: deploy-helper\ndescription: ship it\n---\n# steps\n")
        return "Installed deploy-helper. Chose user scope (no repo option taken)."

    monkeypatch.setattr(skill_install, "_run_claude", fake_run_claude)

    result = worker.execute_command(
        {"id": 1, "type": "skill_install", "payload": {"prompt": "Install deploy-helper from https://skillsmp.example"}}
    )
    assert result["skills"][0] == {
        "name": "deploy-helper",
        "action": "created",
        "extra_files": [],
    }
    assert "user scope" in result["summary"]
    # The pasted prompt is data inside the wrapper, after the non-interactive rules.
    assert "never stop to ask a question" in seen["prompt"]
    assert seen["prompt"].endswith("Install deploy-helper from https://skillsmp.example\n")
    with get_engine().begin() as conn:
        assert repo.get_claude_skill_by_name(conn, "deploy-helper") is not None


def test_skill_install_command_fails_when_nothing_lands(env, monkeypatch):
    monkeypatch.setattr(skill_install, "_run_claude", lambda *a: "I could not fetch it")
    with pytest.raises(worker.CommandError, match="no <skill>/SKILL.md landed"):
        worker.execute_command({"id": 1, "type": "skill_install", "payload": {"prompt": "x"}})
    with pytest.raises(worker.CommandError, match="requires a 'prompt'"):
        worker.execute_command({"id": 1, "type": "skill_install", "payload": {}})


def test_skill_install_route_enqueues(client, auth, lowpriv):
    r = client.post("/claude/skills/install", json={"prompt": "Install x from y"}, headers=auth)
    assert r.status_code == 202
    body = r.json()
    assert body["type"] == "skill_install" and body["status"] == "queued"
    assert body["payload"] == {"prompt": "Install x from y"}

    assert (
        client.post("/claude/skills/install", json={"prompt": "x"}, headers=lowpriv).status_code
        == 403
    )
    empty = client.post("/claude/skills/install", json={"prompt": ""}, headers=auth)
    assert empty.status_code == 422


def test_sync_writes_and_rebuilds_aux_files(env, tmp_path):
    home = str(tmp_path / "home")
    skill = {
        "name": "pdf-tools",
        "description": "d",
        "content": "# body",
        "files": {"references/usage.md": "how-to", "../escape.md": "nope"},
    }
    claude_gen.sync_user_skills([skill], home=home)
    root = tmp_path / "home" / ".claude" / "skills" / "pdf-tools"
    assert (root / "references" / "usage.md").read_text() == "how-to"
    assert not (tmp_path / "home" / ".claude" / "skills" / "escape.md").exists()

    # The dir is rebuilt each sync: files dropped from the DB disappear on disk too.
    claude_gen.sync_user_skills([{**skill, "files": {}}], home=home)
    assert not (root / "references").exists()
    assert (root / "SKILL.md").exists()


# --- spawn integration -----------------------------------------------------------------


def test_spawn_applies_managed_config(env, fake_launch):
    root = env["tmp"] / "proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / ".mise.toml").write_text("[tasks.test]\nrun = 'pytest'\n")
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", str(root))
        repo.create_claude_connector(conn, "github", "stdio", command="npx")
        repo.create_claude_connector(conn, "off", "stdio", command="x", enabled=False)
        repo.create_claude_skill(conn, "deploy", "# steps")
        repo.set_claude_config(conn, "permissions", {"default_mode": "plan"})

    agent = spawn.spawn("proj", "api", task="do it")
    wd = agent["working_dir"]

    # Disabled connectors are excluded from the generated --mcp-config file.
    mcp = json.loads(open(claude_gen.mcp_config_path(wd)).read())
    assert list(mcp["mcpServers"]) == ["github"]
    # Skills synced to the (test-scoped) user-level dir.
    skill = os.path.join(str(env["tmp"]), ".claude", "skills", "deploy", "SKILL.md")
    assert os.path.exists(skill)
    # The generated settings carry the DB permission override.
    settings = json.loads(open(os.path.join(wd, ".claude", "settings.json")).read())
    assert settings["permissions"]["defaultMode"] == "plan"
