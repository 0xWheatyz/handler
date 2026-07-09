"""CI backfill poller: run classification + a full sweep against a faked forge."""

from __future__ import annotations

from handler.control import poller
from handler.db import repository as repo


def test_classify_no_runs_is_pending():
    assert poller.classify([]) == "pending"


def test_classify_any_failure_is_fail():
    runs = [{"conclusion": "success"}, {"conclusion": "failure"}]
    assert poller.classify(runs) == "fail"


def test_classify_all_success_is_pass():
    runs = [{"status": "completed", "conclusion": "success"}]
    assert poller.classify(runs) == "pass"


def test_classify_running_stays_pending():
    runs = [{"status": "in_progress", "conclusion": None}]
    assert poller.classify(runs) == "pending"


def test_classify_tolerates_alternate_spellings():
    assert poller.classify([{"conclusion": "succeeded"}]) == "pass"
    assert poller.classify([{"conclusion": "canceled"}]) == "fail"


def test_classify_action_required_stays_pending_not_pass():
    # A terminal-but-non-success conclusion must NOT be reported as a pass.
    runs = [{"status": "completed", "conclusion": "action_required"}]
    assert poller.classify(runs) == "pending"


def test_classify_status_only_forge_success():
    # No conclusion field at all: fall back to the status.
    assert poller.classify([{"status": "completed"}]) == "pass"


def _seed_pending(conn):
    repo.create_project(conn, "p", "/tmp/p")
    a = repo.create_agent(conn, "p", "a", "/tmp/p/a")
    return repo.insert_log_entry(
        conn, a["id"], status="working", push_sha="sha1", ci_status="pending"
    )


def test_sweep_backfills_pass(engine, fake_forge):
    with engine.begin() as conn:
        entry_id = _seed_pending(conn)
    fake_forge["runs"] = [{"status": "completed", "conclusion": "success"}]

    summary = poller.sweep()
    assert summary == {"checked": 1, "resolved": 1, "pending": 0}
    with engine.begin() as conn:
        assert repo.get_pending_ci_entries(conn) == []
        row = [e for e in repo.get_log(conn, 1) if e["id"] == entry_id][0]
        assert row["ci_status"] == "pass"
        assert row["ci_checked_at"] is not None


def test_sweep_leaves_pending_when_unresolved(engine, fake_forge):
    with engine.begin() as conn:
        _seed_pending(conn)
    fake_forge["runs"] = [{"status": "in_progress"}]
    summary = poller.sweep()
    assert summary["resolved"] == 0
    with engine.begin() as conn:
        assert len(repo.get_pending_ci_entries(conn)) == 1


def test_sweep_leaves_pending_when_forge_unavailable(engine, fake_forge):
    with engine.begin() as conn:
        _seed_pending(conn)
    fake_forge["ci_ok"] = False
    summary = poller.sweep()
    assert summary["resolved"] == 0
    with engine.begin() as conn:
        assert len(repo.get_pending_ci_entries(conn)) == 1


def test_watch_runs_bounded_iterations(engine, fake_forge):
    with engine.begin() as conn:
        _seed_pending(conn)
    fake_forge["runs"] = [{"conclusion": "failure"}]
    summaries = list(poller.watch(iterations=1, interval=0))
    assert len(summaries) == 1
    with engine.begin() as conn:
        assert repo.get_log(conn, 1)[-1]["ci_status"] == "fail"
