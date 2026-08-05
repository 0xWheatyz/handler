"""The bundled ``handler-memory`` MCP server — the agents' read/write path to memory.

A deliberately dependency-free stdio MCP server (newline-delimited JSON-RPC 2.0, the
same wire shape as any ``.mcp.json`` stdio entry): ``claude_gen`` injects it into every
launch's ``--mcp-config`` as ``python -m handler.mcpserver``, and the subprocess
inherits the agent's spawn environment, so identity (``HANDLER_AGENT_ID`` /
``HANDLER_PROJECT_ID``) and ``DATABASE_URL`` arrive exactly the way they do for hooks.
It talks straight to the database — memory is rows, workers stay stateless.

Tools: ``memory_search`` (substring search over the agent's project + global notes;
empty query = most recent), ``memory_get`` (one note with its links), ``memory_save``
(create, or update with ``note_id``), ``memory_link`` (connect two notes, idempotent).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "handler-memory", "version": "0.1.0"}

_NOTE_KINDS = ["fact", "decision", "gotcha", "runbook"]

TOOLS: list[dict] = [
    {
        "name": "memory_search",
        "description": (
            "Search the team memory store (notes left by earlier agent runs and the "
            "operator) for your project plus global notes. Every whitespace-separated "
            "term must match the title, body, or kind (case-insensitive). An empty "
            "query returns the most recent notes. Use this BEFORE re-deriving how "
            "something works — an earlier run may have written it down."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms; empty = recent notes"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
        },
    },
    {
        "name": "memory_get",
        "description": "Fetch one memory note in full, including its links to other notes.",
        "inputSchema": {
            "type": "object",
            "properties": {"note_id": {"type": "integer"}},
            "required": ["note_id"],
        },
    },
    {
        "name": "memory_save",
        "description": (
            "Save durable knowledge for future agent runs: a fact about the system, a "
            "decision and its rationale, a gotcha that cost you time, or a runbook. "
            "Write it for a reader with no context from this session. Pass note_id to "
            "update an existing note instead of creating a new one; pass global=true "
            "only for knowledge that applies across every project."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short, searchable headline"},
                "body": {"type": "string", "description": "The knowledge itself, markdown ok"},
                "kind": {"type": "string", "enum": _NOTE_KINDS, "default": "fact"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "note_id": {"type": "integer", "description": "Update this note instead"},
                "global": {
                    "type": "boolean",
                    "description": "Store unscoped (visible to every project)",
                    "default": False,
                },
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "memory_link",
        "description": (
            "Connect two memory notes so the knowledge graph shows how they relate "
            "(e.g. a gotcha caused_by a decision, a runbook supersedes an older one). "
            "Idempotent: repeating an existing link is fine."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "src_note_id": {"type": "integer"},
                "dst_note_id": {"type": "integer"},
                "relation": {"type": "string", "default": "relates_to"},
            },
            "required": ["src_note_id", "dst_note_id"],
        },
    },
]


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, datetime) else v


def _note_json(note: dict, snippet: bool = False) -> dict:
    out = {k: _iso(v) for k, v in note.items()}
    if snippet and isinstance(out.get("body"), str) and len(out["body"]) > 300:
        out["body"] = out["body"][:300] + "…"
    return out


class MemoryServer:
    """Tool dispatch against the handler database. One short connection per call —
    the process lives as long as the agent's session, but holds nothing in memory."""

    def __init__(self, agent_id: int | None, project_id: str | None):
        self.agent_id = agent_id
        self.project_id = project_id

    def _connection(self):
        from ..db.engine import connection

        return connection()

    # ---- tool implementations ----

    def memory_search(self, args: dict) -> dict:
        from ..db import repository as repo

        query = (args.get("query") or "").strip()
        limit = int(args.get("limit") or 10)
        with self._connection() as conn:
            notes = repo.search_memory_notes(
                conn, query, project_id=self.project_id, limit=limit
            )
        return {
            "count": len(notes),
            "notes": [_note_json(n, snippet=True) for n in notes],
        }

    def memory_get(self, args: dict) -> dict:
        from ..db import repository as repo

        note_id = int(args["note_id"])
        with self._connection() as conn:
            note = repo.get_memory_note(conn, note_id)
            if note is None:
                raise ValueError(f"note {note_id} not found")
            links = repo.list_memory_links(conn, note_ids=[note_id])
            other_ids = {
                (ln["dst_note_id"] if ln["src_note_id"] == note_id else ln["src_note_id"])
                for ln in links
            }
            titles = {
                n["id"]: n["title"]
                for n in (repo.get_memory_note(conn, i) for i in other_ids)
                if n is not None
            }
        return {
            "note": _note_json(note),
            "links": [
                {
                    "id": ln["id"],
                    "src_note_id": ln["src_note_id"],
                    "dst_note_id": ln["dst_note_id"],
                    "relation": ln["relation"],
                    "other_title": titles.get(
                        ln["dst_note_id"] if ln["src_note_id"] == note_id else ln["src_note_id"]
                    ),
                }
                for ln in links
            ],
        }

    def memory_save(self, args: dict) -> dict:
        from ..db import repository as repo

        title = (args.get("title") or "").strip()
        body = (args.get("body") or "").strip()
        if not title or not body:
            raise ValueError("title and body are required")
        kind = args.get("kind") or "fact"
        if kind not in _NOTE_KINDS:
            raise ValueError(f"kind must be one of {_NOTE_KINDS}")
        tags = args.get("tags")
        with self._connection() as conn:
            if args.get("note_id"):
                note_id = int(args["note_id"])
                if repo.get_memory_note(conn, note_id) is None:
                    raise ValueError(f"note {note_id} not found")
                note = repo.update_memory_note(
                    conn, note_id, title=title, body=body, kind=kind, tags=tags
                )
                return {"updated": True, "note": _note_json(note)}
            project_id = None if args.get("global") else self.project_id
            note = repo.create_memory_note(
                conn,
                title=title,
                body=body,
                kind=kind,
                project_id=project_id,
                agent_id=self.agent_id,
                tags=tags,
            )
        return {"created": True, "note": _note_json(note)}

    def memory_link(self, args: dict) -> dict:
        from ..db import repository as repo

        src, dst = int(args["src_note_id"]), int(args["dst_note_id"])
        if src == dst:
            raise ValueError("a note cannot link to itself")
        relation = (args.get("relation") or "relates_to").strip() or "relates_to"
        with self._connection() as conn:
            for note_id in (src, dst):
                if repo.get_memory_note(conn, note_id) is None:
                    raise ValueError(f"note {note_id} not found")
            link = repo.create_memory_link(
                conn, src, dst, relation=relation, agent_id=self.agent_id
            )
        return {"link": {k: _iso(v) for k, v in link.items()}}

    def call_tool(self, name: str, args: dict) -> dict:
        handlers = {
            "memory_search": self.memory_search,
            "memory_get": self.memory_get,
            "memory_save": self.memory_save,
            "memory_link": self.memory_link,
        }
        if name not in handlers:
            raise ValueError(f"unknown tool '{name}'")
        return handlers[name](args)


def handle_message(server: MemoryServer, msg: dict) -> dict | None:
    """One JSON-RPC message in, one response out (None for notifications)."""
    method = msg.get("method")
    msg_id = msg.get("id")

    if msg_id is None:
        return None  # a notification (initialized, cancelled, …) — nothing to answer
    if not method:
        return _error(msg_id, -32600, "invalid request: no method")

    if method == "initialize":
        client_version = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
        return _result(
            msg_id,
            {
                "protocolVersion": client_version,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        )
    if method == "ping":
        return _result(msg_id, {})
    if method == "tools/list":
        return _result(msg_id, {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name") or ""
        args = params.get("arguments") or {}
        try:
            payload = server.call_tool(name, args)
            content = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]
            return _result(msg_id, {"content": content, "isError": False})
        except Exception as exc:  # tool errors go back in-band, per MCP
            content = [{"type": "text", "text": f"error: {exc}"}]
            return _result(msg_id, {"content": content, "isError": True})
    return _error(msg_id, -32601, f"method '{method}' not supported")


def _result(msg_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def serve(stdin=None, stdout=None) -> int:
    """The stdio loop: one JSON-RPC message per line, responses flushed immediately."""
    import os

    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    agent_id_raw = os.environ.get("HANDLER_AGENT_ID")
    server = MemoryServer(
        agent_id=int(agent_id_raw) if agent_id_raw else None,
        project_id=os.environ.get("HANDLER_PROJECT_ID") or None,
    )
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            print(
                json.dumps(_error(None, -32700, "parse error")), file=stdout, flush=True
            )
            continue
        response = handle_message(server, msg)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), file=stdout, flush=True)
    return 0
