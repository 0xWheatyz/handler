"""The ``.mise.toml`` gate — one source of truth for "does this project define the
canonical ``[tasks.test]`` task".

Shared by the spawn gate (``control.spawn.require_test_task``, which refuses to launch an
agent against a project with no test task) and the mise-init Stop hook (which refuses to
let the bootstrap agent finish until the task exists and is committed + pushed).
"""

from __future__ import annotations

import os
import tomllib


def mise_path(working_dir: str) -> str:
    return os.path.join(working_dir, ".mise.toml")


def has_test_task(working_dir: str) -> bool:
    """True when ``.mise.toml`` exists and defines a ``[tasks.test]`` task."""
    path = mise_path(working_dir)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return "test" in (data.get("tasks") or {})
