"""DAL for web management: project/agent mutation, the command queue, and hosts."""

from __future__ import annotations

from handler.db import repository as repo


def test_update_and_delete_project(conn):
    repo.create_project(conn, "p", "/tmp/p", git_remote="https://github.com/me/p.git")
    updated = repo.update_project(conn, "p", git_remote="https://gitea.corp/me/p.git",
                                  credential_ref="env:TOK")
    assert updated["git_remote"] == "https://gitea.corp/me/p.git"
    assert updated["credential_ref"] == "env:TOK"
    # An unknown field is ignored, not applied.
    repo.update_project(conn, "p", nonsense="x")
    assert repo.delete_project(conn, "p") is True
    assert repo.get_project(conn, "p") is None


def test_delete_agent_row(conn):
    repo.create_project(conn, "p", "/tmp/p")
    repo.create_agent(conn, "p", "api", "/tmp/p/api")
    assert repo.delete_agent(conn, "p", "api") is True
    assert repo.get_agent_by_name(conn, "p", "api") is None


def test_delete_project_cascades_all_dependents(conn):
    """A real project always has FK-referencing rows (the sync command, agent history,
    approvals, schedules). Deleting it must clear them, not raise a ForeignKeyViolation."""
    from datetime import UTC, datetime

    repo.create_project(conn, "p", "/tmp/p", git_remote="https://github.com/me/p.git")
    # The sync command queued at registration — the exact row that blocked the delete.
    repo.enqueue_command(conn, "sync", project_id="p", requested_by="operator:web")
    agent = repo.create_agent(conn, "p", "api", "/tmp/p/api")
    repo.insert_log_entry(conn, agent_id=agent["id"], status="working", summary="did work")
    repo.upsert_checkmark_row(conn, agent_id=agent["id"], status="working")
    repo.set_shared_context(conn, "db", "postgres", agent["id"])
    repo.record_approval(conn, "p", "feat/x", "approved", approved_by_agent_id=agent["id"])
    repo.create_schedule(
        conn, "p", "nightly", "run the thing", 3600, datetime.now(UTC)
    )

    assert repo.delete_project(conn, "p") is True

    # Project and everything scoped to it are gone.
    assert repo.get_project(conn, "p") is None
    assert repo.get_agent_by_name(conn, "p", "api") is None
    assert repo.list_commands(conn, project_id="p") == []
    assert repo.list_approvals(conn, "p") == []
    assert repo.list_schedules(conn) == []
    # The global shared-context row survives, with its agent attribution cleared.
    ctx = repo.get_shared_context_key(conn, "db")
    assert ctx is not None and ctx["value"] == "postgres"
    assert ctx["set_by_agent_id"] is None


def test_delete_agent_cascades_log_and_checkmark(conn):
    """Every spawned agent accrues a checkmark + log entries via the hooks; removing the
    agent must clear them rather than trip the log_entries/checkmarks foreign keys."""
    repo.create_project(conn, "p", "/tmp/p")
    agent = repo.create_agent(conn, "p", "api", "/tmp/p/api")
    repo.insert_log_entry(conn, agent_id=agent["id"], status="working", summary="x")
    repo.upsert_checkmark_row(conn, agent_id=agent["id"], status="working")

    assert repo.delete_agent(conn, "p", "api") is True
    assert repo.get_agent_by_name(conn, "p", "api") is None
    assert repo.get_checkmark(conn, agent["id"]) is None
    assert repo.get_log(conn, agent["id"]) == []


def test_enqueue_get_and_list_command(conn):
    repo.create_project(conn, "p", "/tmp/p")
    cmd = repo.enqueue_command(
        conn, "spawn", project_id="p", agent_name="junior",
        payload={"role": "junior"}, requested_by="operator:web",
    )
    assert cmd["status"] == "queued"
    assert cmd["type"] == "spawn"
    assert cmd["payload"] == {"role": "junior"}
    assert repo.get_command(conn, cmd["id"])["agent_name"] == "junior"
    assert [c["id"] for c in repo.list_commands(conn, project_id="p")] == [cmd["id"]]


def test_claim_is_atomic_and_fifo(conn):
    repo.enqueue_command(conn, "poll_ci")
    second = repo.enqueue_command(conn, "poll_ci")

    first_claim = repo.claim_next_command(conn, "worker-1")
    assert first_claim["status"] == "running"
    assert first_claim["claimed_by"] == "worker-1"

    # Oldest-first: the second claim gets the later row, never the same one twice.
    second_claim = repo.claim_next_command(conn, "worker-2")
    assert second_claim["id"] == second["id"]
    assert second_claim["id"] != first_claim["id"]

    # Queue drained -> None.
    assert repo.claim_next_command(conn, "worker-3") is None


def test_finish_command_records_result(conn):
    cmd = repo.enqueue_command(conn, "poll_ci")
    repo.claim_next_command(conn, "w")
    repo.finish_command(conn, cmd["id"], "done", result={"checked": 3})
    done = repo.get_command(conn, cmd["id"])
    assert done["status"] == "done"
    assert done["result"] == {"checked": 3}
    assert done["finished_at"] is not None


def test_hosts_crud(conn):
    created = repo.create_host(conn, "git.corp", "gitea", token_env_var="GITEA_TOKEN")
    assert created["forge_type"] == "gitea"
    assert repo.get_host(conn, "git.corp")["token_env_var"] == "GITEA_TOKEN"
    repo.update_host(conn, "git.corp", base_url="https://git.corp")
    assert repo.get_host(conn, "git.corp")["base_url"] == "https://git.corp"
    assert [h["hostname"] for h in repo.list_hosts(conn)] == ["git.corp"]
    assert repo.delete_host(conn, "git.corp") is True
    assert repo.get_host(conn, "git.corp") is None


def test_operator_approval_has_no_agent_and_lists(conn):
    repo.create_project(conn, "p", "/tmp/p")
    ap = repo.record_approval(conn, "p", "feat/x", "approved", actor="operator:web")
    assert ap["approved_by_agent_id"] is None
    assert ap["actor"] == "operator:web"
    listed = repo.list_approvals(conn, "p")
    assert [a["id"] for a in listed] == [ap["id"]]
    assert repo.list_approvals(conn, "p", branch="other") == []
