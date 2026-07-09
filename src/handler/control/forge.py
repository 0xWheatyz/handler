"""Thin ``forge`` wrapper — the mock seam for forge integration (README 3.6 / 3.7).

Handler shells out to ``forge`` for exactly two jobs: verifying the pinned version at
spawn, and reading CI run status back for the poller. Everything else forge does
(branch creation, PR open, issue linking, merging) is driven by the *agents themselves*
through the generated skills, using the credentials Handler injects — Handler never
opens PRs on their behalf. Keeping our own forge use this small means one seam covers
it, and no live ``forge`` binary is needed in tests.

``forge`` detects the forge type (GitHub/GitLab/Gitea/Forgejo/Bitbucket) from the git
remote, so ``ci list`` / ``ci log`` are the same two commands regardless of host.
"""

from __future__ import annotations

import json
import subprocess

from ..config import get_settings

_TIMEOUT = 120  # seconds; forge CI queries are quick metadata reads, not builds.


def _run(args: list[str], cwd: str) -> tuple[bool, str]:
    forge = get_settings().forge_bin
    try:
        result = subprocess.run(
            [forge, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except FileNotFoundError:
        return False, f"'{forge}' not found"
    except subprocess.TimeoutExpired:
        return False, f"forge {' '.join(args)} timed out after {_TIMEOUT}s"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output.strip()


def check_version(cwd: str = ".") -> tuple[bool, str]:
    """Return ``(matches_pin, reported_version_or_reason)``.

    ``matches_pin`` is True when the configured ``forge_version`` is empty (no pin to
    enforce) or when ``forge --version`` reports a string containing it.
    """
    pin = get_settings().forge_version
    ok, out = _run(["--version"], cwd)
    if not ok:
        return False, out
    if not pin:
        return True, out
    return (pin in out), out


def ci_list(cwd: str, sha: str) -> tuple[bool, list[dict]]:
    """List CI runs for a commit via ``forge ci list``.

    Returns ``(ok, runs)``. ``forge`` is asked for JSON; a run dict is expected to carry
    at least ``status``/``conclusion`` and an ``id``. On any failure ``ok`` is False and
    the list is empty, so the poller simply leaves the entry ``pending`` and retries.
    """
    ok, out = _run(["ci", "list", "--sha", sha, "--json"], cwd)
    if not ok:
        return False, []
    try:
        data = json.loads(out) if out else []
    except json.JSONDecodeError:
        return False, []
    if isinstance(data, dict):
        # Some forges wrap the array, e.g. {"runs": [...]}.
        data = data.get("runs") or data.get("data") or []
    return True, data if isinstance(data, list) else []


def ci_log(cwd: str, run_id: str) -> tuple[bool, str]:
    """Fetch a CI run's log via ``forge ci log <id>`` (for surfacing why it failed)."""
    return _run(["ci", "log", str(run_id)], cwd)
