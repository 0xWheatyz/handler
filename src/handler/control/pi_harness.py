"""The pi harness: run an agent through the lightweight `pi` coding agent instead of
``claude``, keeping every handler behavior (hooks, gates, memory, skills, resume).

Why it exists: ``claude`` is a heavy loop for a local 30B — and it only speaks the
Anthropic Messages API, so a local vLLM/llama.cpp/Ollama endpoint needs a translating
proxy (LiteLLM, claude-code-router) in front of it just to make tool calling work. pi
speaks the OpenAI Completions API natively and carries a fraction of the harness
overhead, so a ``claude_models`` row with ``harness='pi'`` points pi straight at the
bare endpoint. Agents without a model backend (the Claude subscription) are untouched.

The launch is the same shape as claude's: ``pi -p --mode json`` streaming JSON events
on stdout, supervised by :class:`handler.control.headless.RunSupervisor`. Parity with
the claude harness comes from three generated artifacts, all under a per-working-dir
``PI_CODING_AGENT_DIR`` (outside the repo tree, so no gate ever sees them as dirt):

- ``models.json`` + ``settings.json`` — the backend row rendered as a pi provider
  (``openai-completions`` by default) and pinned as the default model; ``settings.json``
  also points pi's skills discovery at the same ``~/.claude/skills`` dir the web-managed
  skill sync maintains (pi implements the same SKILL.md standard), plus the repo's
  committed ``.claude/skills`` (the forge role skills).
- ``extensions/handler-bridge.ts`` — the bundled extension (``pi_bridge.ts``) adapting
  pi's events to ``python -m handler.hooks``: the Stop/test gate, the git-push and
  merge/deploy gates, AskUserQuestion deferral (as an ``ask_operator`` tool), memory
  recall at session start, and the memory tools that claude reaches over MCP.
- ``APPEND_SYSTEM.md`` — the handler conventions appended to pi's system prompt.

Sessions: the launch passes ``--session <dir>/sessions/<uuid>.jsonl`` explicitly, so the
transcript is a single file at a path handler chose — pre-assignable like claude's
``--session-id``, trivially archivable for cross-worker resume, and resuming is just
launching again with the same path (verified: pi creates the file on first use and
appends on subsequent runs).

The task prompt travels via **stdin**, not argv: pi merges piped stdin into the prompt
and has no ``--`` separator, so argv delivery would misparse a task starting with ``-``.
"""

from __future__ import annotations

import json
import os
import sys
from importlib import resources
from pathlib import Path

from ..config import get_settings

PROVIDER_NAME = "handler"
BRIDGE_FILENAME = "handler-bridge.ts"

# Sensible local-endpoint defaults for pi model entries; overridable per row via the
# env map keys below (the same escape hatch claude rows use for endpoint quirks).
_DEFAULT_CONTEXT_WINDOW = 128_000
_DEFAULT_MAX_TOKENS = 16_384

# Row ``env`` keys the pi harness interprets itself (everything else passes through to
# the process environment unchanged):
#   PI_PROVIDER_API    — pi api dialect (default "openai-completions"; also accepts
#                        "anthropic-messages", "openai-responses", …)
#   PI_CONTEXT_WINDOW  — advertised context window for the model entries
#   PI_MAX_TOKENS      — max output tokens for the model entries
_CONFIG_KEYS = {"PI_PROVIDER_API", "PI_CONTEXT_WINDOW", "PI_MAX_TOKENS"}

_SYSTEM_APPEND = """\
## Handler agent contract

You are an unattended background agent supervised by handler. No human watches this
terminal, and plain-text questions go nowhere.

- **Questions**: when genuinely blocked on a decision only the operator can make, call
  the `ask_operator` tool. The run pauses; the operator's answer arrives when the
  session resumes. Never invent credentials or guess at destructive choices.
- **Completion gate**: you are only done when the project's test task (`mise run test`)
  passes AND your work is committed AND pushed. Ending the session runs this gate; a
  failure sends the blockers back to you — fix them rather than re-explaining.
- **Pushing**: `git push` is gated the same way (tests, then a throwaway image build
  when the project defines one). A denied push tells you exactly why.
- **Team memory**: search it with `memory_search` before re-deriving how something
  works — earlier runs may have written it down. Save durable findings (facts,
  decisions, gotchas, runbooks) with `memory_save`; connect related notes with
  `memory_link`.
"""


def _munged(working_dir: str) -> str:
    """Same path-munging claude uses for its per-cwd session dirs (see
    ``headless.munged_project_dir``): stable, filesystem-safe, layout-invariant across
    workers that share ``PROJECTS_ROOT``."""
    return working_dir.replace("/", "-").replace(".", "-")


def pi_dir(working_dir: str) -> Path:
    """The per-working-dir ``PI_CODING_AGENT_DIR`` — pi's whole config universe for this
    agent (models, settings, extensions, sessions). Under ``$HOME`` and not the repo
    tree, so the clean-tree completion gate never trips on generated files."""
    return Path(os.path.expanduser("~")) / ".handler-pi" / _munged(working_dir)


def sessions_dir(working_dir: str) -> Path:
    return pi_dir(working_dir) / "sessions"


def session_file(working_dir: str, session_id: str) -> Path:
    """The transcript path handler pre-assigns via ``--session`` (pi creates it)."""
    return sessions_dir(working_dir) / f"{session_id}.jsonl"


def bridge_path(working_dir: str) -> Path:
    return pi_dir(working_dir) / "extensions" / BRIDGE_FILENAME


def _model_entries(row: dict) -> list[dict]:
    env = row.get("env") or {}
    try:
        context_window = int(env.get("PI_CONTEXT_WINDOW", _DEFAULT_CONTEXT_WINDOW))
    except (TypeError, ValueError):
        context_window = _DEFAULT_CONTEXT_WINDOW
    try:
        max_tokens = int(env.get("PI_MAX_TOKENS", _DEFAULT_MAX_TOKENS))
    except (TypeError, ValueError):
        max_tokens = _DEFAULT_MAX_TOKENS
    ids: list[str] = [row["model"]]
    small = row.get("small_fast_model")
    if small and small not in ids:
        ids.append(small)
    return [
        {
            "id": model_id,
            "name": model_id,
            "reasoning": False,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": context_window,
            "maxTokens": max_tokens,
        }
        for model_id in ids
    ]


def write_config(working_dir: str, row: dict, api_key: str) -> Path:
    """Materialize the pi config dir for one launch (spawn and resume both, like
    ``claude_gen.apply``): provider + default model from the backend row, the bridge
    extension, the skills pointers, and the system-prompt append. Regenerated every
    launch so a row edit reaches the next run."""
    base = pi_dir(working_dir)
    (base / "extensions").mkdir(parents=True, exist_ok=True)
    sessions_dir(working_dir).mkdir(parents=True, exist_ok=True)

    env = row.get("env") or {}
    provider = {
        "name": PROVIDER_NAME,
        "baseUrl": row["base_url"],
        "api": env.get("PI_PROVIDER_API") or "openai-completions",
        # pi hides models until the provider has *some* credential; local endpoints
        # accept anything, and the placeholder never leaks a real secret.
        "apiKey": api_key,
        "models": _model_entries(row),
    }
    with open(base / "models.json", "w") as fh:
        json.dump({"providers": {PROVIDER_NAME: provider}}, fh, indent=2)

    settings = {
        "defaultProvider": PROVIDER_NAME,
        "defaultModel": row["model"],
        # pi implements the same SKILL.md standard as claude: reuse the web-managed
        # sync's user-level dir, plus the repo's committed skills (forge roles).
        "skills": [
            os.path.join(os.path.expanduser("~"), ".claude", "skills"),
            os.path.join(working_dir, ".claude", "skills"),
        ],
    }
    with open(base / "settings.json", "w") as fh:
        json.dump(settings, fh, indent=2)

    bridge_src = resources.files("handler.control").joinpath("pi_bridge.ts").read_text()
    with open(bridge_path(working_dir), "w") as fh:
        fh.write(bridge_src)

    with open(base / "APPEND_SYSTEM.md", "w") as fh:
        fh.write(_SYSTEM_APPEND)
    return base


def agent_env(working_dir: str, row: dict) -> dict[str, str]:
    """The env overrides a pi-harness agent launches with (the pi analog of the
    ``ANTHROPIC_*`` set): pi's config dir, offline startup (a local endpoint serves no
    update checks), and the interpreter the bridge shells hooks out to. Row env extras
    win over everything, minus the keys the config writer already consumed."""
    env = {
        "PI_CODING_AGENT_DIR": str(pi_dir(working_dir)),
        "PI_OFFLINE": "1",
        "HANDLER_PYTHON": sys.executable,
    }
    for k, v in (row.get("env") or {}).items():
        if str(k) not in _CONFIG_KEYS:
            env[str(k)] = str(v)
    return env


def build_argv(session_id: str, working_dir: str) -> list[str]:
    """The headless pi invocation — identical for spawn and resume, because the
    pre-assigned ``--session`` file either doesn't exist yet (spawn: pi creates it) or
    carries the history (resume: pi appends). The prompt is NOT here: it is piped to
    stdin by the supervisor (pi has no ``--`` separator, so argv can't safely carry an
    arbitrary task). ``--no-extensions`` disables discovery — the bridge is the one
    extension, loaded explicitly — so a managed repo can't inject code into the run."""
    s = get_settings()
    return [
        s.pi_bin,
        "-p",
        "--mode", "json",
        "--no-extensions",
        "-e", str(bridge_path(working_dir)),
        "--session", str(session_file(working_dir, session_id)),
    ]
