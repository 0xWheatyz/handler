"""The headless runner: worker-owned ``claude -p`` subprocesses streaming to the DB.

This is the tmux replacement seam for agent *runs* (tmux stays only for the interactive
``/login`` flow). Each invocation is ``claude -p --output-format stream-json`` with a
pre-assigned ``--session-id``; a :class:`RunSupervisor` owns the child process, appends
every stdout JSON line to ``agent_events`` as it arrives, derives ``agents.last_output``
from the latest assistant text (so the existing UI keeps working), and reconciles the
agent's status from the *process* — exit code and EOF are positive liveness, replacing
the old pane scraping that could neither see a dead process nor populate the log.

Resume continuity without shared files: claude persists its session under
``~/.claude/projects/<munged-cwd>/``; the supervisor tars that into ``session_archives``
(periodically and at exit), and whichever worker later claims a resume materializes the
archive at the same munged path before running ``claude -p --resume``. Workers therefore
need the same ``projects_root`` layout — a deployment invariant — but share nothing.

``launch()`` is the function ``spawn``/``worker`` call and tests mock (via the
``claude_bin`` setting pointing at a fake, same pattern as the tmux fakes).
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tarfile
import tempfile
import threading
import time
import uuid
from pathlib import Path

from ..config import get_settings
from ..db import repository as repo
from ..db.engine import connection

# Stream types we recognize from ``--output-format stream-json``; anything else (or an
# unparseable line) is stored as-is so no output is ever dropped. ``worker`` is our own:
# runner-generated notices (crashes, archive failures, degraded resumes).
_KNOWN_TYPES = ("system", "assistant", "user", "result", "hook")

# How long a SIGTERM'd claude gets to die before SIGKILL.
_TERM_GRACE_SECONDS = 10.0


def munged_project_dir(working_dir: str) -> str:
    """The directory name claude uses for a cwd under ``~/.claude/projects/``.

    Claude munges the absolute path by mapping ``/`` and ``.`` to ``-`` (verified against
    real session state: ``/root/handler`` → ``-root-handler``,
    ``/root/Talos/.claude/worktrees/x`` → ``-root-Talos--claude-worktrees-x``).
    """
    return working_dir.replace("/", "-").replace(".", "-")


def session_dir(working_dir: str) -> Path:
    """Where claude persists sessions for ``working_dir`` (under the *current* $HOME)."""
    return Path(os.path.expanduser("~")) / ".claude" / "projects" / munged_project_dir(working_dir)


def build_spawn_argv(task: str, settings_path: str, session_id: str) -> list[str]:
    """The headless spawn invocation. ``--verbose`` is required with stream-json in
    print mode; ``--session-id`` pre-assigns the UUID so the session is addressable
    (and archivable) from the first event."""
    s = get_settings()
    argv = [
        s.claude_bin, "-p", "--verbose",
        "--output-format", "stream-json",
        "--session-id", session_id,
        "--settings", settings_path,
    ]
    if s.run_budget_usd > 0:
        argv += ["--max-budget-usd", str(s.run_budget_usd)]
    argv += ["--", task]
    return argv


def build_resume_argv(session_id: str, answer: str, settings_path: str) -> list[str]:
    """The headless resume invocation — a brand-new process continuing ``session_id``."""
    s = get_settings()
    argv = [
        s.claude_bin, "-p", "--verbose",
        "--output-format", "stream-json",
        "--resume", session_id,
        "--settings", settings_path,
    ]
    if s.run_budget_usd > 0:
        argv += ["--max-budget-usd", str(s.run_budget_usd)]
    argv += ["--", answer]
    return argv


def parse_stream_line(line: str) -> tuple[str, dict]:
    """One stdout line → ``(event_type, payload)``. Never raises: malformed JSON or an
    unrecognized shape comes back as ``("raw", {"line": ...})`` so the event log keeps
    everything the process said, even across CLI format drift."""
    text = line.strip()
    if not text:
        return "raw", {"line": line}
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return "raw", {"line": line}
    if not isinstance(payload, dict):
        return "raw", {"line": line}
    etype = payload.get("type")
    if not isinstance(etype, str) or not etype:
        return "raw", payload
    if etype not in _KNOWN_TYPES:
        # Future/unknown top-level types still store under their own name — the UI
        # ignores what it doesn't know, but nothing is lost.
        return etype, payload
    return etype, payload


def assistant_text(payload: dict) -> str | None:
    """The concatenated text blocks of an ``assistant`` event, or None when it carries
    none (e.g. a pure tool_use turn). Feeds ``agents.last_output``."""
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content or None
    if not isinstance(content, list):
        return None
    parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    text = "\n".join(p for p in parts if p)
    return text or None


def archive_session(working_dir: str, session_id: str, max_bytes: int | None = None) -> bytes | None:
    """Tar.gz the session transcript + sidecar dir, or None when nothing exists yet or
    the result would exceed ``max_bytes`` (the caller records a worker event; the run
    itself is unaffected — only cross-worker resume degrades)."""
    base = session_dir(working_dir)
    jsonl = base / f"{session_id}.jsonl"
    sidecar = base / session_id
    if not jsonl.exists() and not sidecar.exists():
        return None
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        if jsonl.exists():
            tar.add(jsonl, arcname=jsonl.name)
        if sidecar.is_dir():
            tar.add(sidecar, arcname=sidecar.name)
    data = buf.getvalue()
    limit = max_bytes if max_bytes is not None else get_settings().session_archive_max_bytes
    if limit and len(data) > limit:
        return None
    return data


def materialize_session(working_dir: str, archive: bytes) -> None:
    """Unpack a session archive where claude will look for it on ``--resume``.

    ``filter="data"`` rejects path traversal and special members — the archive came from
    our own DB, but a defense-in-depth default costs nothing.
    """
    base = session_dir(working_dir)
    base.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        tar.extractall(base, filter="data")


class RunSupervisor:
    """Owns one headless claude subprocess for its whole life.

    A reader thread pumps stdout lines into ``agent_events``; the supervisor thread
    watches the process, polls ``cancel_requested`` (cross-worker kill), uploads the
    session archive periodically, and on exit reconciles run + agent status. Threads are
    daemons: if the whole worker dies, the reaper — not us — settles the record.
    """

    def __init__(
        self,
        agent: dict,
        run: dict,
        argv: list[str],
        cwd: str,
        env: dict[str, str],
        *,
        cancel_poll: float = 5.0,
        archive_interval: float = 60.0,
        on_exit=None,
    ) -> None:
        self.agent = agent
        self.run = run
        self.argv = argv
        self.cwd = cwd
        self.env = env
        self.cancel_poll = cancel_poll
        self.archive_interval = archive_interval
        self.on_exit = on_exit  # worker's slot-release callback
        self._seq = 0
        self._result_payload: dict | None = None
        self._canceled = False
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self._supervise, name=f"run-{self.run['id']}", daemon=True
        )
        self.thread.start()

    # ---------------------------------------------------------------- internals

    def _insert_event(self, etype: str, payload: dict) -> None:
        self._seq += 1
        with connection() as conn:
            repo.insert_agent_event(
                conn,
                self.agent["id"],
                self.run["id"],
                seq=self._seq,
                type=etype,
                payload=payload,
                session_id=self.run["session_id"],
            )

    def _pump_stdout(self, stream) -> None:
        for line in stream:
            etype, payload = parse_stream_line(line)
            try:
                self._insert_event(etype, payload)
                if etype == "result":
                    self._result_payload = payload
                elif etype == "assistant":
                    text = assistant_text(payload)
                    if text:
                        with connection() as conn:
                            repo.update_agent_output(conn, self.agent["id"], text)
            except Exception:  # noqa: BLE001 - a DB hiccup must not sever the pipe
                continue

    def _upload_archive(self) -> None:
        try:
            data = archive_session(self.cwd, self.run["session_id"])
            if data is None:
                return
            with connection() as conn:
                repo.upsert_session_archive(
                    conn, self.agent["id"], self.run["session_id"], data
                )
        except Exception as exc:  # noqa: BLE001 - archiving is best-effort
            try:
                self._insert_event(
                    "worker", {"notice": "session archive failed", "error": str(exc)}
                )
            except Exception:  # noqa: BLE001
                pass

    def _terminate(self, proc: subprocess.Popen) -> None:
        self._canceled = True
        proc.terminate()
        try:
            proc.wait(timeout=_TERM_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()

    def _supervise(self) -> None:
        stderr_file = tempfile.TemporaryFile()
        try:
            proc = subprocess.Popen(
                self.argv,
                cwd=self.cwd,
                env={**os.environ, **self.env},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=stderr_file,
                text=True,
            )
        except OSError as exc:
            stderr_file.close()
            self._settle(exit_code=None, stderr_tail=f"failed to launch claude: {exc}")
            return
        reader = threading.Thread(
            target=self._pump_stdout, args=(proc.stdout,), daemon=True
        )
        reader.start()
        last_archive = time.monotonic()
        next_cancel_check = time.monotonic() + self.cancel_poll
        while proc.poll() is None:
            time.sleep(0.2)
            now = time.monotonic()
            if now >= next_cancel_check:
                next_cancel_check = now + self.cancel_poll
                with connection() as conn:
                    if repo.get_cancel_requested(conn, self.run["id"]):
                        self._terminate(proc)
                        break
            if self.archive_interval > 0 and now - last_archive >= self.archive_interval:
                self._upload_archive()
                last_archive = now
        proc.wait()
        reader.join(timeout=30.0)
        stderr_file.seek(0)
        stderr_tail = stderr_file.read()[-4000:].decode("utf-8", "replace")
        stderr_file.close()
        self._settle(exit_code=proc.returncode, stderr_tail=stderr_tail)

    def _settle(self, exit_code: int | None, stderr_tail: str) -> None:
        """Reconcile run + agent status once the process is gone, then final-archive."""
        result = self._result_payload
        clean = (
            exit_code == 0
            and result is not None
            and not result.get("is_error", False)
        )
        if self._canceled:
            run_status = "canceled"
        elif clean:
            run_status = "completed"
        else:
            run_status = "failed"
        try:
            with connection() as conn:
                finished = repo.finish_run(
                    conn, self.run["id"], run_status, exit_code=exit_code, result=result
                )
                # Hooks are the authority on agent status — they ran inside the run and
                # may have set paused_for_input/blocked/done already. Only an agent still
                # marked ``working`` needs the process's verdict.
                agent = repo.get_agent_by_id(conn, self.agent["id"])
                if finished and agent is not None and agent["status"] == "working":
                    if self._canceled:
                        repo.set_agent_status(conn, self.agent["id"], "done")
                    elif clean:
                        repo.set_agent_status(conn, self.agent["id"], "done")
                    else:
                        repo.set_agent_status(conn, self.agent["id"], "blocked")
            if not clean and not self._canceled:
                detail = {"notice": "run failed", "exit_code": exit_code}
                if stderr_tail.strip():
                    detail["stderr_tail"] = stderr_tail
                self._insert_event("worker", detail)
        except Exception:  # noqa: BLE001 - never let bookkeeping raise out of the thread
            pass
        self._upload_archive()
        if self.on_exit is not None:
            try:
                self.on_exit(self)
            except Exception:  # noqa: BLE001
                pass


def launch(
    agent: dict,
    *,
    kind: str,
    prompt: str,
    settings_path: str,
    env: dict[str, str],
    worker_id: str,
    on_exit=None,
) -> dict:
    """Start a headless run for ``agent`` and return its ``agent_runs`` row.

    ``kind`` is ``spawn`` (fresh session, new UUID) or ``resume`` (materialize the stored
    archive, continue the agent's existing session). Fire-and-forget from the caller's
    perspective — the returned run row is already ``running`` and a daemon supervisor
    owns the process from here.
    """
    working_dir = agent["working_dir"]
    if kind == "spawn":
        session_id = str(uuid.uuid4())
        argv = build_spawn_argv(prompt, settings_path, session_id)
    else:
        session_id = agent.get("session_id")
        if not session_id:
            raise ValueError(f"agent '{agent['name']}' has no session to resume")
        argv = build_resume_argv(session_id, prompt, settings_path)
    with connection() as conn:
        run = repo.create_run(conn, agent["id"], session_id, worker_id, kind)
        repo.set_agent_session(conn, agent["id"], session_id, worker_id)
    supervisor = RunSupervisor(
        agent, run, argv, cwd=working_dir, env=env, on_exit=on_exit
    )
    supervisor.start()
    return run
