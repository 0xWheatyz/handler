"""Agent memory: the notes/links DAL, the /memory API, the bundled handler-memory MCP
server, and the SessionStart recall hook."""

from __future__ import annotations

import json

import pytest

from handler.db import repository as repo
from handler.db.engine import get_engine


@pytest.fixture
def seeded(env):
    """Two projects, one agent, and a small note graph."""
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", "/tmp/proj")
        repo.create_project(conn, "other", "/tmp/other")
        agent = repo.create_agent(conn, "proj", "api", "/tmp/proj", "working")
        n1 = repo.create_memory_note(
            conn, "Auth flow", "Tokens are minted in deps.py", "fact",
            project_id="proj", agent_id=agent["id"], tags=["auth"],
        )
        n2 = repo.create_memory_note(
            conn, "Use SQLite fallback", "Postgres is default, SQLite for tests",
            "decision", project_id="proj",
        )
        n3 = repo.create_memory_note(
            conn, "Global runbook", "How to rotate tokens", "runbook",
        )
        n4 = repo.create_memory_note(
            conn, "Other-project note", "Not visible from proj scope", "fact",
            project_id="other",
        )
        link = repo.create_memory_link(
            conn, n1["id"], n2["id"], relation="caused_by", agent_id=agent["id"]
        )
    return {"agent": agent, "n1": n1, "n2": n2, "n3": n3, "n4": n4, "link": link}


# --- DAL -------------------------------------------------------------------------------


def test_scoped_listing_and_search(seeded):
    with get_engine().begin() as conn:
        # Project scope = its notes + global, newest first; never another project's.
        notes = repo.list_memory_notes(conn, project_id="proj")
        ids = [n["id"] for n in notes]
        assert seeded["n4"]["id"] not in ids
        assert {seeded["n1"]["id"], seeded["n2"]["id"], seeded["n3"]["id"]} <= set(ids)

        # Every term must match; case-insensitive over title/body/kind.
        hits = repo.search_memory_notes(conn, "auth tokens", project_id="proj")
        assert [h["id"] for h in hits] == [seeded["n1"]["id"]]
        # Empty query = recent notes in scope.
        assert repo.search_memory_notes(conn, "", project_id="proj")
        # kind matches too.
        assert any(
            h["id"] == seeded["n3"]["id"]
            for h in repo.search_memory_notes(conn, "runbook", project_id="proj")
        )


def test_link_idempotent_and_graph_scope(seeded):
    with get_engine().begin() as conn:
        again = repo.create_memory_link(
            conn, seeded["n1"]["id"], seeded["n2"]["id"], relation="caused_by"
        )
        assert again["id"] == seeded["link"]["id"]  # re-asserting is not a new edge

        # A cross-scope link's edge drops out of a scoped graph when one endpoint is out.
        repo.create_memory_link(conn, seeded["n1"]["id"], seeded["n4"]["id"])
        graph = repo.memory_graph(conn, project_id="proj")
        graph_ids = {n["id"] for n in graph["notes"]}
        assert seeded["n4"]["id"] not in graph_ids
        assert [ln["id"] for ln in graph["links"]] == [seeded["link"]["id"]]


def test_delete_note_removes_edges(seeded):
    with get_engine().begin() as conn:
        assert repo.delete_memory_note(conn, seeded["n2"]["id"])
        assert repo.get_memory_note(conn, seeded["n2"]["id"]) is None
        assert repo.list_memory_links(conn, note_ids=[seeded["n1"]["id"]]) == []


def test_agent_delete_keeps_notes_project_delete_removes_them(seeded):
    with get_engine().begin() as conn:
        # Deleting the authoring agent orphans the attribution, never the knowledge.
        assert repo.delete_agent(conn, "proj", "api")
        note = repo.get_memory_note(conn, seeded["n1"]["id"])
        assert note is not None and note["agent_id"] is None
        link = repo.get_memory_link(conn, seeded["link"]["id"])
        assert link is not None and link["created_by_agent_id"] is None

        # Deleting the project takes its notes (and their edges); global notes stay.
        assert repo.delete_project(conn, "proj")
        assert repo.get_memory_note(conn, seeded["n1"]["id"]) is None
        assert repo.get_memory_note(conn, seeded["n2"]["id"]) is None
        assert repo.get_memory_note(conn, seeded["n3"]["id"]) is not None


# --- API -------------------------------------------------------------------------------


def test_api_note_crud_and_graph(client, auth, seeded):
    r = client.post(
        "/memory/notes",
        json={"title": "From the dashboard", "body": "operator wisdom", "kind": "gotcha"},
        headers=auth,
    )
    assert r.status_code == 201
    note = r.json()
    assert note["agent_id"] is None and note["project_id"] is None

    r = client.patch(f"/memory/notes/{note['id']}", json={"kind": "runbook"}, headers=auth)
    assert r.status_code == 200 and r.json()["kind"] == "runbook"

    r = client.get("/memory/notes?q=wisdom", headers=auth)
    assert [n["id"] for n in r.json()] == [note["id"]]

    r = client.get("/memory/graph?project_id=proj", headers=auth)
    graph = r.json()
    assert {n["id"] for n in graph["notes"]} >= {seeded["n1"]["id"], seeded["n3"]["id"]}
    assert graph["links"][0]["relation"] == "caused_by"

    assert client.delete(f"/memory/notes/{note['id']}", headers=auth).status_code == 200
    assert client.get(f"/memory/notes/{note['id']}", headers=auth).status_code == 404


def test_api_validation(client, auth, seeded):
    n1 = seeded["n1"]["id"]
    # Unknown project scope on create; self-links; missing endpoints.
    r = client.post(
        "/memory/notes",
        json={"title": "x", "body": "y", "project_id": "nope"},
        headers=auth,
    )
    assert r.status_code == 400
    r = client.post(
        "/memory/links", json={"src_note_id": n1, "dst_note_id": n1}, headers=auth
    )
    assert r.status_code == 400
    r = client.post(
        "/memory/links", json={"src_note_id": n1, "dst_note_id": 999999}, headers=auth
    )
    assert r.status_code == 404
    # Bad kind is a 422 straight from the schema.
    r = client.post("/memory/notes", json={"title": "x", "body": "y", "kind": "poem"}, headers=auth)
    assert r.status_code == 422
    # No token, no memory.
    assert client.get("/memory/notes").status_code == 401


# --- MCP server ------------------------------------------------------------------------


def _rpc(server, method, params=None, msg_id=1):
    from handler.mcpserver import handle_message

    return handle_message(server, {"jsonrpc": "2.0", "id": msg_id, "method": method,
                                   "params": params or {}})


def _call_tool(server, name, args):
    resp = _rpc(server, "tools/call", {"name": name, "arguments": args})
    result = resp["result"]
    return result["isError"], json.loads(result["content"][0]["text"]) if not result[
        "isError"
    ] else result["content"][0]["text"]


def test_mcp_protocol_basics(seeded):
    from handler.mcpserver import MemoryServer, handle_message

    server = MemoryServer(agent_id=seeded["agent"]["id"], project_id="proj")
    init = _rpc(server, "initialize", {"protocolVersion": "2025-06-18"})
    assert init["result"]["serverInfo"]["name"] == "handler-memory"
    assert init["result"]["protocolVersion"] == "2025-06-18"
    # Notifications get no response; unknown methods error.
    assert handle_message(server, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert _rpc(server, "resources/list")["error"]["code"] == -32601
    tools = _rpc(server, "tools/list")["result"]["tools"]
    # The bundled server's whole surface: the memory tools plus dispatch (tested in
    # tests/test_dispatch.py), which shares this transport and identity contract.
    assert {t["name"] for t in tools} == {
        "memory_search", "memory_get", "memory_save", "memory_link", "dispatch_agent",
    }


def test_mcp_tools_roundtrip(seeded):
    from handler.mcpserver import MemoryServer

    server = MemoryServer(agent_id=seeded["agent"]["id"], project_id="proj")

    err, saved = _call_tool(server, "memory_save", {
        "title": "Worker heartbeats", "body": "Reaper marks stale workers crashed",
        "kind": "fact", "tags": ["workers"],
    })
    assert not err and saved["created"]
    assert saved["note"]["project_id"] == "proj"
    assert saved["note"]["agent_id"] == seeded["agent"]["id"]

    err, found = _call_tool(server, "memory_search", {"query": "heartbeats"})
    assert not err and found["count"] == 1

    # Search sees global notes; never the other project's.
    err, found = _call_tool(server, "memory_search", {"query": "rotate tokens"})
    assert not err and found["count"] == 1
    err, found = _call_tool(server, "memory_search", {"query": "Other-project"})
    assert not err and found["count"] == 0

    err, linked = _call_tool(server, "memory_link", {
        "src_note_id": saved["note"]["id"], "dst_note_id": seeded["n1"]["id"],
        "relation": "relates_to",
    })
    assert not err and linked["link"]["created_by_agent_id"] == seeded["agent"]["id"]

    err, got = _call_tool(server, "memory_get", {"note_id": saved["note"]["id"]})
    assert not err
    assert got["links"][0]["other_title"] == "Auth flow"

    # Update in place via note_id.
    err, updated = _call_tool(server, "memory_save", {
        "note_id": saved["note"]["id"], "title": "Worker heartbeats",
        "body": "expanded", "kind": "gotcha",
    })
    assert not err and updated["updated"]

    # Tool errors come back in-band, not as protocol errors.
    err, msg = _call_tool(server, "memory_get", {"note_id": 424242})
    assert err and "not found" in msg


def test_mcp_global_save(seeded):
    from handler.mcpserver import MemoryServer

    server = MemoryServer(agent_id=None, project_id="proj")
    err, saved = _call_tool(server, "memory_save", {
        "title": "For everyone", "body": "x", "global": True,
    })
    assert not err and saved["note"]["project_id"] is None


# --- SessionStart recall hook + launch wiring ------------------------------------------


def test_session_start_hook_injects_notes(seeded, capsys):
    from handler.hooks import memory_ctx
    from handler.hooks.context import HookInput, Identity

    ident = Identity(seeded["agent"]["id"], "proj", "api", "/tmp/proj")
    with get_engine().begin() as conn:
        result = memory_ctx.handle(conn, ident, HookInput(raw={}, event="session_start"))
    ctx = result["hookSpecificOutput"]["additionalContext"]
    assert result["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Auth flow" in ctx and "Global runbook" in ctx
    assert "Other-project note" not in ctx
    assert "memory_search" in ctx  # the pointer at the tools
    # The hook wrote its JSON response to stdout for claude to consume.
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]


def test_settings_wire_session_start_and_memory_allow(env):
    from handler.control import settings_gen

    settings = settings_gen.build_settings()
    hook = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert hook.endswith("-m handler.hooks session_start")
    assert "mcp__handler-memory" in settings["permissions"]["allow"]
