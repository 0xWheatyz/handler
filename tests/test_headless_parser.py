"""Pure-helper tests for the headless runner: stream parsing, path munging, argv
construction, and the session archive round-trip. No subprocess is launched here —
the process-level tests live in test_headless_run.py (phase 2)."""

from __future__ import annotations

import io
import tarfile

from handler.control import headless


# ------------------------------------------------------------------ parse_stream_line


def test_parse_valid_event_types():
    for etype in ("system", "assistant", "user", "result", "hook"):
        parsed_type, payload = headless.parse_stream_line(f'{{"type": "{etype}", "x": 1}}\n')
        assert parsed_type == etype
        assert payload == {"type": etype, "x": 1}


def test_parse_unknown_type_keeps_its_name():
    parsed_type, payload = headless.parse_stream_line('{"type": "telemetry", "n": 2}')
    assert parsed_type == "telemetry"
    assert payload["n"] == 2


def test_parse_garbage_becomes_raw():
    parsed_type, payload = headless.parse_stream_line("this is not json\n")
    assert parsed_type == "raw"
    assert payload == {"line": "this is not json\n"}


def test_parse_non_dict_json_becomes_raw():
    parsed_type, payload = headless.parse_stream_line('["a", "b"]')
    assert parsed_type == "raw"


def test_parse_missing_type_becomes_raw():
    parsed_type, payload = headless.parse_stream_line('{"message": "no type field"}')
    assert parsed_type == "raw"
    assert payload == {"message": "no type field"}


def test_parse_blank_line_becomes_raw():
    parsed_type, _ = headless.parse_stream_line("   \n")
    assert parsed_type == "raw"


# -------------------------------------------------------------------- assistant_text


def test_assistant_text_joins_text_blocks():
    payload = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "first"},
                {"type": "tool_use", "name": "Bash", "input": {}},
                {"type": "text", "text": "second"},
            ]
        },
    }
    assert headless.assistant_text(payload) == "first\nsecond"


def test_assistant_text_none_for_pure_tool_use():
    payload = {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]},
    }
    assert headless.assistant_text(payload) is None


def test_assistant_text_string_content():
    assert headless.assistant_text({"message": {"content": "plain"}}) == "plain"


def test_assistant_text_missing_message():
    assert headless.assistant_text({"type": "assistant"}) is None


# ---------------------------------------------------------------- munged_project_dir


def test_munge_matches_recorded_real_examples():
    # Recorded from a real ~/.claude/projects/ (see plan): '/' and '.' both map to '-'.
    assert headless.munged_project_dir("/root/handler") == "-root-handler"
    assert (
        headless.munged_project_dir("/root/Talos/.claude/worktrees/mise-tooling")
        == "-root-Talos--claude-worktrees-mise-tooling"
    )


# ------------------------------------------------------------------- argv builders


def test_spawn_argv_shape(env):
    argv = headless.build_spawn_argv("do the task", "/wd/.claude/settings.json", "sid-1")
    assert argv[0] == "claude"
    assert "-p" in argv and "--verbose" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[argv.index("--session-id") + 1] == "sid-1"
    assert argv[argv.index("--settings") + 1] == "/wd/.claude/settings.json"
    assert "--max-budget-usd" not in argv  # default budget is 0 = off
    assert argv[-2:] == ["--", "do the task"]
    assert "--resume" not in argv


def test_resume_argv_shape(env):
    argv = headless.build_resume_argv("sid-2", "the answer", "/wd/.claude/settings.json")
    assert argv[argv.index("--resume") + 1] == "sid-2"
    assert argv[-2:] == ["--", "the answer"]
    assert "--session-id" not in argv


def test_spawn_argv_includes_budget_when_set(env, monkeypatch):
    monkeypatch.setenv("RUN_BUDGET_USD", "2.5")
    from handler import config

    config.get_settings.cache_clear()
    argv = headless.build_spawn_argv("t", "/s.json", "sid")
    assert argv[argv.index("--max-budget-usd") + 1] == "2.5"
    config.get_settings.cache_clear()


# ------------------------------------------------------------- archive round-trip


def _write_fake_session(home, working_dir: str, session_id: str) -> None:
    base = home / ".claude" / "projects" / headless.munged_project_dir(working_dir)
    base.mkdir(parents=True)
    (base / f"{session_id}.jsonl").write_text('{"type": "user", "prompt": "hi"}\n')
    sidecar = base / session_id / "tool-results"
    sidecar.mkdir(parents=True)
    (sidecar / "r1.txt").write_text("tool output")


def test_archive_and_materialize_round_trip(env, tmp_path, monkeypatch):
    working_dir = "/projects/demo"
    _write_fake_session(tmp_path, working_dir, "sid-rt")

    data = headless.archive_session(working_dir, "sid-rt")
    assert data is not None

    # Materialize onto a *different* worker: a fresh HOME with no session state.
    other_home = tmp_path / "other-worker"
    other_home.mkdir()
    monkeypatch.setenv("HOME", str(other_home))
    headless.materialize_session(working_dir, data)

    base = other_home / ".claude" / "projects" / headless.munged_project_dir(working_dir)
    assert (base / "sid-rt.jsonl").read_text() == '{"type": "user", "prompt": "hi"}\n'
    assert (base / "sid-rt" / "tool-results" / "r1.txt").read_text() == "tool output"


def test_archive_none_when_no_session(env):
    assert headless.archive_session("/projects/none", "missing-sid") is None


def test_archive_refuses_oversize(env, tmp_path):
    working_dir = "/projects/big"
    _write_fake_session(tmp_path, working_dir, "sid-big")
    assert headless.archive_session(working_dir, "sid-big", max_bytes=10) is None


def test_archive_contains_only_session_members(env, tmp_path):
    working_dir = "/projects/demo2"
    _write_fake_session(tmp_path, working_dir, "sid-a")
    # A sibling session must not leak into sid-a's archive.
    base = tmp_path / ".claude" / "projects" / headless.munged_project_dir(working_dir)
    (base / "sid-other.jsonl").write_text("{}\n")

    data = headless.archive_session(working_dir, "sid-a")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        names = tar.getnames()
    assert all(n == "sid-a.jsonl" or n.startswith("sid-a") for n in names)
