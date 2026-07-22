#!/usr/bin/env python3
"""A stand-in ``claude`` binary for headless-runner tests.

Wired in via the existing ``claude_bin`` setting (the same seam the tmux fakes used).
Parses the real headless argv, emits a scripted ``--output-format stream-json`` stream on
stdout, and writes a genuine session transcript + sidecar under
``$HOME/.claude/projects/<munged-cwd>/`` so archive/materialize/resume paths exercise the
real filesystem layout. Behavior is selected with ``FAKE_CLAUDE_MODE``:

- ``success`` (default): init + assistant + result, exit 0.
- ``error``: init + assistant + one garbage line, then exit 2 with no result event.
- ``hang``: init, then sleep forever (the kill/cancel/reaper tests SIGTERM it).
- ``slow``: like success with a pause between events (concurrency tests).
- ``resume-fail``: a ``--resume`` invocation exits 1 before any assistant event
  (exercises the context re-injection fallback).

On ``--resume`` (outside resume-fail) the transcript materialized by the worker MUST
already exist at the expected path — missing means cross-worker materialization broke,
so the fake fails loudly, exit 3.
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
        "verbose": False,
        "output_format": None,
        "session_id": None,
        "resume": None,
        "settings": None,
        "budget": None,
        "prompt": None,
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-p":
            opts["print"] = True
        elif arg == "--verbose":
            opts["verbose"] = True
        elif arg == "--output-format":
            i += 1
            opts["output_format"] = argv[i]
        elif arg == "--session-id":
            i += 1
            opts["session_id"] = argv[i]
        elif arg in ("--resume", "-r"):
            i += 1
            opts["resume"] = argv[i]
        elif arg == "--settings":
            i += 1
            opts["settings"] = argv[i]
        elif arg == "--max-budget-usd":
            i += 1
            opts["budget"] = argv[i]
        elif arg == "--":
            opts["prompt"] = " ".join(argv[i + 1 :])
            break
        else:
            opts["prompt"] = arg
        i += 1
    return opts


def _munged(cwd: str) -> str:
    return cwd.replace("/", "-").replace(".", "-")


def _emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def _write_transcript(session_id: str, prompt: str) -> None:
    base = Path(os.path.expanduser("~")) / ".claude" / "projects" / _munged(os.getcwd())
    base.mkdir(parents=True, exist_ok=True)
    jsonl = base / f"{session_id}.jsonl"
    with jsonl.open("a") as fh:
        fh.write(json.dumps({"type": "user", "prompt": prompt}) + "\n")
        fh.write(json.dumps({"type": "assistant", "text": f"handled: {prompt}"}) + "\n")
    sidecar = base / session_id / "tool-results"
    sidecar.mkdir(parents=True, exist_ok=True)
    (sidecar / "result-1.txt").write_text("fake tool output\n")


def main() -> int:
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    mode = os.environ.get("FAKE_CLAUDE_MODE", "success")
    opts = _parse_argv(sys.argv[1:])
    if not opts["print"] or opts["output_format"] != "stream-json":
        sys.stderr.write("fake_claude: expected -p --output-format stream-json\n")
        return 64

    session_id = opts["session_id"] or opts["resume"] or "fake-session"
    prompt = opts["prompt"] or ""

    if mode == "resume-fail" and opts["resume"]:
        sys.stderr.write("fake_claude: no conversation found to resume\n")
        return 1

    if opts["resume"]:
        base = Path(os.path.expanduser("~")) / ".claude" / "projects" / _munged(os.getcwd())
        if not (base / f"{session_id}.jsonl").exists():
            sys.stderr.write(f"fake_claude: transcript missing at {base}\n")
            return 3

    _emit(
        {
            "type": "system",
            "subtype": "init",
            "session_id": session_id,
            "cwd": os.getcwd(),
            "tools": ["Bash", "Read", "Edit"],
        }
    )
    if mode == "hang":
        time.sleep(3600)
        return 0
    if mode == "slow":
        time.sleep(float(os.environ.get("FAKE_CLAUDE_SLOW_SECONDS", "1.0")))

    _emit(
        {
            "type": "assistant",
            "session_id": session_id,
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": f"working on: {prompt}"}],
            },
        }
    )
    _write_transcript(session_id, prompt)

    if mode == "error":
        sys.stdout.write("this is not json\n")
        sys.stdout.flush()
        return 2

    _emit(
        {
            "type": "result",
            "subtype": "success",
            "session_id": session_id,
            "is_error": False,
            "num_turns": 1,
            "total_cost_usd": 0.01,
            "result": f"done: {prompt}",
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
