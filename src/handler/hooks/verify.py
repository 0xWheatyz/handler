"""The verification helpers — the mock seam for the gates.

``run_test`` / ``run_build`` shell ``mise run <task>`` in the agent's working dir and
report ``(ok, output)``. Hook decision logic is tested by faking these two functions,
so no live ``mise``/``kaniko`` is needed. A missing ``mise`` is treated as a failure
with a clear reason — the test task is a hard requirement, so a silent skip would
defeat the gate.
"""

from __future__ import annotations

import subprocess

from ..config import get_settings

_TIMEOUT = 1800  # seconds; long enough for a real suite/build, bounded so a hang fails.


def _run_mise_task(task: str, cwd: str) -> tuple[bool, str]:
    mise = get_settings().mise_bin
    try:
        result = subprocess.run(
            [mise, "run", task],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except FileNotFoundError:
        return False, f"'{mise}' not found: cannot run the '{task}' gate"
    except subprocess.TimeoutExpired:
        return False, f"'{task}' timed out after {_TIMEOUT}s"

    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output.strip()


def run_test(cwd: str) -> tuple[bool, str]:
    return _run_mise_task("test", cwd)


def run_build(cwd: str) -> tuple[bool, str]:
    """Throwaway image build (kaniko/buildah, no registry) via ``mise run build-image``."""
    return _run_mise_task("build-image", cwd)
