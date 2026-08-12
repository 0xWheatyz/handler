#!/usr/bin/env python3
"""A stand-in ``pi`` binary for pi-harness headless-runner tests.

Wired in via the ``pi_bin`` setting (the same seam ``fake_claude.py`` uses for
``claude_bin``). Parses the real pi-harness argv (``-p --mode json --no-extensions
-e <bridge> --session <path>``), reads the prompt from **stdin** (pi has no ``--``
separator, so that is how the supervisor delivers it), emits a scripted ``--mode json``
event stream on stdout, and appends to the genuine ``--session`` transcript file so
archive/materialize/resume paths exercise the real single-file layout. Behavior is
selected with ``FAKE_PI_MODE``:

- ``success`` (default): session header + user/assistant message_end + agent_end +
  agent_settled, exit 0.
- ``error``: header + one garbage line + agent_end whose assistant stopReason is
  ``error``, then exit 1 (pi's exit code for an errored final message).
- ``hang``: header, then sleep forever (kill/cancel tests SIGTERM it).

``FAKE_PI_EXPECT_HISTORY=1`` makes a run fail loudly (exit 3) when the ``--session``
file does not already exist — the cross-worker resume tests use it to prove the
archive really was materialized where pi would look.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path


def _parse_argv(argv: list[str]) -> dict:
    opts = {
        "print": False,
        "mode": None,
        "no_extensions": False,
        "extension": None,
        "session": None,
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-p":
            opts["print"] = True
        elif arg == "--mode":
            i += 1
            opts["mode"] = argv[i]
        elif arg == "--no-extensions":
            opts["no_extensions"] = True
        elif arg == "-e":
            i += 1
            opts["extension"] = argv[i]
        elif arg == "--session":
            i += 1
            opts["session"] = argv[i]
        i += 1
    return opts


def _emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def _assistant(text: str) -> dict:
    return {
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "stopReason": "stop",
    }


def main() -> int:
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    mode = os.environ.get("FAKE_PI_MODE", "success")
    opts = _parse_argv(sys.argv[1:])
    if not opts["print"] or opts["mode"] != "json" or not opts["session"]:
        sys.stderr.write("fake_pi: expected -p --mode json --session <path>\n")
        return 64
    if not opts["no_extensions"] or not opts["extension"]:
        sys.stderr.write("fake_pi: expected --no-extensions with an explicit -e bridge\n")
        return 64

    prompt = sys.stdin.read().strip()
    session_path = Path(opts["session"])
    is_resume = session_path.exists()
    if os.environ.get("FAKE_PI_EXPECT_HISTORY") and not is_resume:
        sys.stderr.write(f"fake_pi: session file missing at {session_path}\n")
        return 3

    _emit({"type": "session", "version": 3, "id": "internal-uuid", "cwd": os.getcwd()})
    if mode == "hang":
        time.sleep(3600)
        return 0

    user_msg = {"role": "user", "content": [{"type": "text", "text": prompt}]}
    _emit({"type": "agent_start"})
    _emit({"type": "message_end", "message": user_msg})
    if mode == "error":
        sys.stdout.write("this is not json\n")
        sys.stdout.flush()
        errored = {
            "role": "assistant",
            "content": [],
            "stopReason": "error",
            "errorMessage": "Connection error.",
        }
        _emit({"type": "agent_end", "messages": [user_msg, errored], "willRetry": False})
        return 1

    assistant = _assistant(f"working on: {prompt}")
    _emit({"type": "message_end", "message": assistant})

    session_path.parent.mkdir(parents=True, exist_ok=True)
    with session_path.open("a") as fh:
        fh.write(json.dumps({"type": "message", "message": user_msg}) + "\n")
        fh.write(json.dumps({"type": "message", "message": assistant}) + "\n")

    _emit({"type": "agent_end", "messages": [user_msg, assistant], "willRetry": False})
    _emit({"type": "agent_settled"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
