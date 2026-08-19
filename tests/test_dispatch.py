"""Agent-initiated dispatch: the ``dispatch_agent`` MCP tool, its guardrails, and the
depth that spawn recovers for the agents it launches.

A dispatch is an ordinary queued ``spawn`` command attributed to the agent that asked
for it, so these tests assert on the command queue — the same rows Activity renders.
"""

from __future__ import annotations

import json

import pytest

from handler.db import repository as repo
from handler.db.engine import get_engine


@pytest.fixture
def dispatcher(env):
    """A project with one agent that has a live run (the per-run budget's boundary)."""
    with get_engine().begin() as conn:
        repo.create_project(conn, "proj", "/tmp/proj")
        repo.create_project(conn, "other", "/tmp/other")
        agent = repo.create_agent(conn, "proj", "scout-1", "/tmp/proj", "working")
        run = repo.create_run(conn, agent["id"], "s1", "w1", "spawn")
    return {"agent": agent, "run": run}


_DEFAULT = object()


def _server(dispatcher, *, depth=0, project_id="proj", agent_id=_DEFAULT):
    from handler.mcpserver import MemoryServer

    return MemoryServer(
        agent_id=dispatcher["agent"]["id"] if agent_id is _DEFAULT else agent_id,
        project_id=project_id,
        dispatch_depth=depth,
    )


def _call(server, name, args):
    from handler.mcpserver import handle_message

    resp = handle_message(
        server,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": name, "arguments": args}},
    )
    result = resp["result"]
    text = result["content"][0]["text"]
    return result["isError"], (text if result["isError"] else json.loads(text))


_TASK = {"name_prefix": "planner", "task": "Read @specs/x.md and build it", "reason": "new paper"}


# --- the happy path ----------------------------------------------------------------------


def test_dispatch_enqueues_an_attributed_spawn(dispatcher):
    err, out = _call(_server(dispatcher), "dispatch_agent", {**_TASK, "role": "planner"})
    assert not err, out
    assert out["dispatched"] is True
    assert out["agent_name"].startswith("planner-")

    with get_engine().begin() as conn:
        command = repo.get_command(conn, out["command_id"])
    assert command["type"] == "spawn"
    assert command["status"] == "queued"
    assert command["project_id"] == "proj"
    assert command["agent_name"] == out["agent_name"]
    # Attribution is what makes a dispatch legible in Activity — and what the per-run
    # budget counts.
    assert command["requested_by"] == f"agent:{dispatcher['agent']['id']}"
    payload = command["payload"]
    assert payload["task"] == _TASK["task"]
    assert payload["reason"] == _TASK["reason"]
    assert payload["role"] == "planner"
    assert payload["dispatch_depth"] == 1
    assert payload["parent_agent_id"] == dispatcher["agent"]["id"]


def test_dispatch_is_listed_and_optional_fields_pass_through(dispatcher):
    from handler.mcpserver import TOOLS

    assert "dispatch_agent" in {t["name"] for t in TOOLS}

    err, out = _call(
        _server(dispatcher),
        "dispatch_agent",
        {**_TASK, "model_id": 7, "worktree": "feature/x", "subdir": "svc"},
    )
    assert not err, out
    with get_engine().begin() as conn:
        payload = repo.get_command(conn, out["command_id"])["payload"]
    assert payload["model_id"] == 7
    assert payload["worktree"] == "feature/x"
    assert payload["subdir"] == "svc"
    # Untouched optional fields stay absent rather than arriving as nulls the worker
    # would have to special-case.
    assert "role" not in payload


def test_repeat_dispatches_get_distinct_names(dispatcher):
    """Names are timestamped to the second; a burst must not collide."""
    server = _server(dispatcher)
    names = set()
    for _ in range(3):
        err, out = _call(server, "dispatch_agent", _TASK)
        assert not err, out
        names.add(out["agent_name"])
    assert len(names) == 3


# --- guardrails --------------------------------------------------------------------------


def test_project_comes_from_the_environment_not_the_arguments(dispatcher):
    """Project isolation holds by construction: a foreign project_id is simply ignored."""
    err, out = _call(_server(dispatcher), "dispatch_agent", {**_TASK, "project_id": "other"})
    assert not err, out
    with get_engine().begin() as conn:
        assert repo.get_command(conn, out["command_id"])["project_id"] == "proj"


def test_per_run_budget_refuses_the_next_dispatch(dispatcher, monkeypatch):
    monkeypatch.setenv("MAX_DISPATCH_PER_RUN", "2")
    from handler import config

    config.get_settings.cache_clear()
    server = _server(dispatcher)
    for _ in range(2):
        err, out = _call(server, "dispatch_agent", _TASK)
        assert not err, out

    err, msg = _call(server, "dispatch_agent", _TASK)
    assert err
    assert "dispatch refused" in msg and "limit 2" in msg
    with get_engine().begin() as conn:
        queued = [c for c in repo.list_commands(conn, project_id="proj") if c["type"] == "spawn"]
    assert len(queued) == 2
    config.get_settings.cache_clear()


def test_budget_counts_only_the_current_run(dispatcher, monkeypatch):
    """A dispatch from an earlier run doesn't spend this run's allowance."""
    monkeypatch.setenv("MAX_DISPATCH_PER_RUN", "1")
    from handler import config

    config.get_settings.cache_clear()
    server = _server(dispatcher)
    err, _ = _call(server, "dispatch_agent", _TASK)
    assert not err
    err, _ = _call(server, "dispatch_agent", _TASK)
    assert err  # budget spent for this run

    # A new run resets the window.
    with get_engine().begin() as conn:
        repo.finish_run(conn, dispatcher["run"]["id"], "completed", exit_code=0)
        repo.create_run(conn, dispatcher["agent"]["id"], "s2", "w1", "resume")
    err, out = _call(server, "dispatch_agent", _TASK)
    assert not err, out
    config.get_settings.cache_clear()


def test_depth_cap_refuses_a_long_chain(dispatcher, monkeypatch):
    monkeypatch.setenv("MAX_DISPATCH_DEPTH", "3")
    from handler import config

    config.get_settings.cache_clear()
    # Depth 2 may still hand off (the child lands at 3, the cap itself).
    err, out = _call(_server(dispatcher, depth=2), "dispatch_agent", _TASK)
    assert not err, out
    assert out["dispatch_depth"] == 3
    # Depth 3 is the end of the chain: a cycle terminates here instead of fanning out.
    err, msg = _call(_server(dispatcher, depth=3), "dispatch_agent", _TASK)
    assert err
    assert "dispatch refused" in msg and "deep" in msg
    config.get_settings.cache_clear()


@pytest.mark.parametrize(
    "args",
    [
        {**_TASK, "name_prefix": "  "},
        {**_TASK, "task": ""},
        {**_TASK, "reason": ""},
        {**_TASK, "role": "architect"},
    ],
)
def test_bad_arguments_are_refused(dispatcher, args):
    err, msg = _call(_server(dispatcher), "dispatch_agent", args)
    assert err
    assert "error:" in msg


def test_dispatch_needs_an_identity(dispatcher):
    """A process with no agent identity (a stray CLI call) cannot enqueue work."""
    err, msg = _call(_server(dispatcher, agent_id=None), "dispatch_agent", _TASK)
    assert err
    assert "identity" in msg


# --- what the dispatched agent inherits --------------------------------------------------


def test_spawn_recovers_dispatch_depth_for_the_child(dispatcher):
    """The child's depth is read back off the command that created it — so it survives
    a resume, which carries no payload of its own."""
    from handler.control import spawn

    err, out = _call(_server(dispatcher, depth=1), "dispatch_agent", _TASK)
    assert not err, out
    assert spawn._dispatch_depth("proj", out["agent_name"]) == 2
    # An operator- or schedule-started agent is at the root of its own chain.
    assert spawn._dispatch_depth("proj", "scout-1") == 0


def test_dispatch_reaches_the_call_seam(dispatcher, monkeypatch, capsys):
    """``--call`` is how pi-harness agents dispatch; it shares the tool implementation."""
    import io

    from handler.mcpserver.__main__ import call_tool

    monkeypatch.setenv("HANDLER_AGENT_ID", str(dispatcher["agent"]["id"]))
    monkeypatch.setenv("HANDLER_PROJECT_ID", "proj")
    monkeypatch.setenv("HANDLER_DISPATCH_DEPTH", "1")
    out = io.StringIO()
    rc = call_tool("dispatch_agent", stdin=io.StringIO(json.dumps(_TASK)), stdout=out)
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["dispatched"] is True
    # The env-carried depth is what the seam uses, same as the MCP path.
    assert payload["dispatch_depth"] == 2
