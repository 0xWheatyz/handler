"""Hook dispatch: ``python -m handler.hooks <event>``.

Events: ``stop``, ``session_end``, ``pre_tool_use``, ``notification``. Reads the event
JSON on stdin, resolves the acting agent, dispatches, and exits 0. A resolution failure
or unexpected error exits nonzero with a stderr message but never crashes the agent's
turn in a way that loses data.
"""

from __future__ import annotations

import sys

from ..db.engine import connection
from . import checkpoint, gate, notify
from .context import read_input, resolve_identity

_EVENTS = {"stop", "session_end", "pre_tool_use", "notification"}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in _EVENTS:
        print(f"usage: python -m handler.hooks {{{'|'.join(sorted(_EVENTS))}}}", file=sys.stderr)
        return 2
    event = argv[0]

    hook_input = read_input(event)

    with connection() as conn:
        ident = resolve_identity(conn, hook_input)
        if ident is None:
            print("handler hook: could not resolve agent identity", file=sys.stderr)
            return 1

        if event in ("stop", "session_end"):
            checkpoint.handle(conn, ident, hook_input)
        elif event == "pre_tool_use":
            gate.handle(conn, ident, hook_input)
        elif event == "notification":
            notify.handle(conn, ident, hook_input)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
