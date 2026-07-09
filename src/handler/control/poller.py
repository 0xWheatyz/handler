"""CI status backfill poller (README 3.6, Phase 2).

CI is the authoritative build-and-deploy gate; Handler just closes the loop on it. When
the push gate clears a push, it records a log entry with ``push_sha`` and
``ci_status = 'pending'``. This poller — a control-layer process, not a hook, since CI
can take minutes — sweeps those pending entries, asks ``forge ci list`` for the runs tied
to each commit, and backfills ``ci_status`` / ``ci_checked_at`` once a run resolves.

Same two forge commands regardless of host (``forge`` detects the forge from the remote),
so this is one poller against one interface, not per-host integration. It's built as a
one-shot :func:`sweep` (drive cadence with cron/systemd) plus an optional :func:`watch`
loop for setups with no external scheduler.
"""

from __future__ import annotations

import time

from ..db import repository as repo
from ..db.engine import connection
from . import forge

# A CI run's terminal "it failed" conclusions, however the forge spells them.
_FAIL_CONCLUSIONS = {"failure", "failed", "error", "cancelled", "canceled", "timed_out"}
# Explicit success *conclusions* (GitHub-style). A terminal-but-non-success conclusion
# such as ``action_required`` / ``neutral`` / ``stale`` is deliberately NOT here, so it
# stays pending rather than masquerading as a pass.
_SUCCESS_CONCLUSIONS = {"success", "succeeded", "passed"}
# Success-ish *statuses*, used only when a run reports no conclusion field at all
# (status-only forges); when a conclusion is present it must be judged on its own.
_SUCCESS_STATUSES = {"completed", "success", "passed"}


def _run_field(run: dict, *names: str) -> str:
    for name in names:
        value = run.get(name)
        if isinstance(value, str) and value:
            return value.lower()
    return ""


def classify(runs: list[dict]) -> str:
    """Reduce forge's CI runs for a commit to ``pass`` | ``fail`` | ``pending``.

    Conservative: any resolved failure -> ``fail``; all runs resolved and successful ->
    ``pass``; anything still queued/running, or no runs yet, stays ``pending`` so the
    poller keeps checking rather than declaring a verdict early.
    """
    if not runs:
        return "pending"
    all_resolved = True
    for run in runs:
        conclusion = _run_field(run, "conclusion", "result")
        status = _run_field(run, "status", "state")
        if conclusion in _FAIL_CONCLUSIONS:
            return "fail"
        if conclusion:
            # A conclusion is present: it must be an explicit success to count as done.
            resolved = conclusion in _SUCCESS_CONCLUSIONS
        else:
            # No conclusion field (status-only forge): fall back to the status.
            resolved = status in _SUCCESS_STATUSES
        if not resolved:
            all_resolved = False
    return "pass" if all_resolved else "pending"


def sweep(project_id: str | None = None) -> dict:
    """One pass over pending pushes. Returns counts: checked / resolved / still pending."""
    with connection() as conn:
        entries = repo.get_pending_ci_entries(conn, project_id=project_id)

    checked = resolved = 0
    for entry in entries:
        checked += 1
        ok, runs = forge.ci_list(entry["working_dir"], entry["push_sha"])
        if not ok:
            # forge unavailable / remote hiccup — leave it pending and retry next sweep.
            continue
        verdict = classify(runs)
        if verdict == "pending":
            continue
        with connection() as conn:
            repo.update_ci_status(conn, entry["id"], verdict)
        resolved += 1
    return {"checked": checked, "resolved": resolved, "pending": checked - resolved}


def watch(project_id: str | None = None, interval: float = 30.0, iterations: int | None = None):
    """Loop :func:`sweep` forever (or ``iterations`` times, for tests), sleeping between.

    Yields each sweep's summary so a caller/test can observe progress without capturing
    stdout.
    """
    count = 0
    while iterations is None or count < iterations:
        yield sweep(project_id=project_id)
        count += 1
        if iterations is not None and count >= iterations:
            break
        time.sleep(interval)
