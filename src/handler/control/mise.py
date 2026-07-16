"""The mise-config gate — one source of truth for "does this project define the canonical
``[tasks.test]`` task".

Shared by the spawn gate (``control.spawn.require_test_task``, which refuses to launch an
agent against a project with no test task) and the mise-init Stop hook (which refuses to
let the bootstrap agent finish until the task exists and is committed + pushed).

mise reads several config filenames, not just ``.mise.toml`` — a repo may ship ``mise.toml``
(no leading dot) or keep config under ``.config/mise/`` — so the gate accepts any of them
and treats a ``[tasks.test]`` in *any* present config as satisfying the requirement.
"""

from __future__ import annotations

import os
import tomllib

# The config filenames mise itself looks for, in the rough precedence order it uses. A
# project only needs one; we scan all present ones for the test task.
CONFIG_NAMES = (
    "mise.toml",
    ".mise.toml",
    "mise.local.toml",
    ".mise.local.toml",
    os.path.join(".config", "mise.toml"),
    os.path.join(".config", "mise", "config.toml"),
)


def config_paths(working_dir: str) -> list[str]:
    return [os.path.join(working_dir, name) for name in CONFIG_NAMES]


def existing_config(working_dir: str) -> str | None:
    """Path to the first present mise config file under ``working_dir``, else ``None``."""
    for path in config_paths(working_dir):
        if os.path.exists(path):
            return path
    return None


def has_config(working_dir: str) -> bool:
    return existing_config(working_dir) is not None


def has_test_task(working_dir: str) -> bool:
    """True when any present mise config defines a ``[tasks.test]`` task."""
    for path in config_paths(working_dir):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as fh:
                data = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if "test" in (data.get("tasks") or {}):
            return True
    return False
