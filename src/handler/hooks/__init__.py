"""Claude Code hook entrypoints — the backend's write path.

Invoked as ``python -m handler.hooks <event>`` from the per-agent settings.json. Each
hook reads the event JSON on stdin, resolves its agent identity from the environment
(injected at spawn), writes checkmark/log rows, and returns the event's response
contract on stdout.
"""
