"""Phase 2 CLI: approve/reject (env identity), poll-ci, forge-init."""

from __future__ import annotations

from handler.control import cli
from handler.db import repository as repo
from handler.db.engine import get_engine


def _seed_project_agent(role="senior", name="senior"):
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", "/tmp/p")
        return repo.create_agent(conn, "p", name, "/tmp/p/s", role=role)


def test_approve_via_cli_uses_env_identity(env, monkeypatch, capsys):
    agent = _seed_project_agent()
    monkeypatch.setenv("HANDLER_PROJECT_ID", "p")
    monkeypatch.setenv("HANDLER_AGENT_ID", str(agent["id"]))

    rc = cli.main(["approve", "--branch", "feat/x", "--pr", "7", "--note", "lgtm"])
    assert rc == 0
    with get_engine().begin() as conn:
        latest = repo.get_latest_approval(conn, "p", "feat/x")
    assert latest["status"] == "approved"
    assert latest["approved_by_agent_id"] == agent["id"]
    assert latest["pr_ref"] == "7"


def test_reject_via_cli(env, monkeypatch):
    agent = _seed_project_agent()
    monkeypatch.setenv("HANDLER_PROJECT_ID", "p")
    monkeypatch.setenv("HANDLER_AGENT_ID", str(agent["id"]))
    assert cli.main(["reject", "--branch", "feat/x", "--note", "fix it"]) == 0
    with get_engine().begin() as conn:
        assert repo.get_latest_approval(conn, "p", "feat/x")["status"] == "rejected"


def test_approve_without_identity_errors(env, monkeypatch, capsys):
    _seed_project_agent()
    monkeypatch.delenv("HANDLER_PROJECT_ID", raising=False)
    monkeypatch.delenv("HANDLER_AGENT_ID", raising=False)
    assert cli.main(["approve", "--branch", "feat/x"]) == 1
    assert "no project" in capsys.readouterr().err


def test_approve_rejects_unknown_agent(env, monkeypatch, capsys):
    _seed_project_agent()
    monkeypatch.setenv("HANDLER_PROJECT_ID", "p")
    monkeypatch.setenv("HANDLER_AGENT_ID", "9999")
    assert cli.main(["approve", "--branch", "feat/x"]) == 1
    assert "not found" in capsys.readouterr().err


def test_poll_ci_cli(env, fake_forge, capsys):
    with get_engine().begin() as conn:
        repo.create_project(conn, "p", "/tmp/p")
        a = repo.create_agent(conn, "p", "a", "/tmp/p/a")
        repo.insert_log_entry(conn, a["id"], status="working", push_sha="s", ci_status="pending")
    fake_forge["runs"] = [{"conclusion": "success"}]
    assert cli.main(["poll-ci"]) == 0
    assert "resolved=1" in capsys.readouterr().out


def test_forge_init_writes_and_commits(env, fake_gitops, capsys):
    root = env["tmp"] / "proj"
    root.mkdir(parents=True, exist_ok=True)
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", str(root))

    assert cli.main(["forge-init", "--project", "proj"]) == 0
    assert (root / ".claude" / "skills" / "forge-junior" / "SKILL.md").exists()
    # Auto-committed via the git seam.
    assert len(fake_gitops["commit"]) == 1


def test_forge_init_unknown_project_errors(env, capsys):
    assert cli.main(["forge-init", "--project", "nope"]) == 1
    assert "not registered" in capsys.readouterr().err
