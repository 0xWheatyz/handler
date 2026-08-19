"""``python -m handler.mcpserver`` — run the bundled handler-memory MCP server.

``--call <tool>`` runs one tool directly instead: JSON arguments on stdin, JSON
result on stdout, exit 1 with the error on stderr for a failed call. This is the seam
the pi harness's bridge extension uses (pi has no MCP by design), sharing the exact
tool implementations — and the same identity-from-environment contract — the MCP
server dispatches to.
"""

from __future__ import annotations

import json
import sys

from . import serve, server_from_env


def call_tool(name: str, stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    raw = stdin.read()
    try:
        args = json.loads(raw) if raw.strip() else {}
    except ValueError:
        print("invalid JSON arguments on stdin", file=sys.stderr)
        return 2
    server = server_from_env()
    try:
        payload = server.call_tool(name, args if isinstance(args, dict) else {})
    except Exception as exc:  # noqa: BLE001 - the caller renders this as a tool error
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False), file=stdout, flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) >= 2 and argv[0] == "--call":
        return call_tool(argv[1])
    return serve()


if __name__ == "__main__":
    sys.exit(main())
