"""The schema — one ``MetaData``, six tables, mapping README section 3.1 exactly.

SQLAlchemy Core (not the ORM): the workload is a handful of explicit statements, and
Core keeps the same schema rendering correctly on both dialects with no session
lifecycle to manage across the API, CLI, and hook subprocesses.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
)

from .types import PortableBigInt, PortableJSON, PortableTimestamp

metadata = MetaData()

# Status vocabularies kept as free TEXT (README uses plain strings, not PG enums, so
# both dialects match). CheckConstraints make the allowed sets explicit and portable.
# ``crashed`` is reserved for the reaper: it marks an agent whose owning worker went
# silent mid-run — never a normal exit, which reconciles to done/blocked instead.
AGENT_STATUSES = ("working", "paused_for_input", "blocked", "done", "crashed")
GATE_STATUSES = ("pass", "fail", "unknown")
CI_STATUSES = ("not_applicable", "pending", "pass", "fail")
VISIBILITIES = ("project", "global")
APPROVAL_STATUSES = ("approved", "rejected")
# The control actions the API enqueues and the control-container worker executes.
# ``sync`` clones a project's repo into its root_dir (or fast-forward pulls an existing
# clone) using the git server's stored credentials — the API can't run git itself.
# ``login_start``/``login_submit`` drive the bundled ``claude`` binary's ``/login`` OAuth
# flow from the web UI: the worker opens an interactive claude session in the control
# container, returns the claude.com authorization URL, and later feeds back the pasted
# code — the API container has no ``claude`` and can't run it directly.
# ``skill_install`` runs an operator-pasted marketplace install prompt through a one-off
# headless claude in a staging dir and imports what it fetched as managed skill rows.
COMMAND_TYPES = (
    "spawn",
    "kill",
    "resume",
    "approve",
    "reject",
    "forge_init",
    "mise_init",
    "poll_ci",
    "sync",
    "login_start",
    "login_submit",
    "skill_install",
)
COMMAND_STATUSES = ("queued", "running", "done", "failed")
# Forge families a host can belong to (drives per-host token env conventions).
FORGE_TYPES = ("github", "gitlab", "gitea", "forgejo", "bitbucket")
# One agent_runs row per headless ``claude -p`` invocation (spawn or resume).
# ``canceled`` = an operator kill; ``crashed`` = the reaper found the owning worker dead.
RUN_KINDS = ("spawn", "resume")
RUN_STATUSES = ("running", "completed", "failed", "crashed", "canceled")


def _in(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"


projects = Table(
    "projects",
    metadata,
    Column("id", String, primary_key=True),  # slug, e.g. "leeworks-api"
    Column("root_dir", String, nullable=False),
    Column("git_remote", String),
    # Pointer to a secret (env:VAR / file:/path / cmd:...), never the token — README 3.7.
    Column("credential_ref", String),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
)

agents = Table(
    "agents",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("project_id", String, ForeignKey("projects.id"), nullable=False),
    Column("name", String, nullable=False),  # unique within a project, not globally
    Column("working_dir", String, nullable=False),
    Column("status", String, nullable=False),
    # Optional workflow role (junior | senior | deploy) — informational, drives which
    # forge skill an agent follows; the approval gate keys on identity, not role.
    Column("role", String),
    # A periodic snapshot of the agent's live tmux pane tail (last ~40 lines), refreshed by
    # the control worker's poll loop. The tmux socket lives only in the control container,
    # so this DB column is how the API/UI see what a running — or wedged — agent is doing.
    # Headless runs reuse it, derived from the latest assistant text instead of a pane tail.
    Column("last_output", String),
    Column("output_at", PortableTimestamp),
    # Headless runner (null on legacy tmux agents — the rollout discriminator): the claude
    # session UUID pre-assigned at spawn (stable across resumes), and the worker currently
    # (or last) supervising a run for this agent.
    Column("session_id", String),
    Column("worker_id", String),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    UniqueConstraint("project_id", "name", name="uq_agents_project_name"),
    CheckConstraint(_in("status", AGENT_STATUSES), name="ck_agents_status"),
)

log_entries = Table(
    "log_entries",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("agent_id", BigInteger, ForeignKey("agents.id"), nullable=False),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    Column("session_id", String),
    Column("status", String, nullable=False),
    Column("summary", String),
    Column("decisions", String),
    Column("question", String),
    Column("answer", String),  # filled in on resume; only field ever touched post-insert
    Column("visibility", String, nullable=False, server_default="project"),
    Column("push_sha", String),  # set if this checkpoint pushed; null otherwise
    Column("ci_status", String, nullable=False, server_default="not_applicable"),
    Column("ci_checked_at", PortableTimestamp),
    CheckConstraint(_in("visibility", VISIBILITIES), name="ck_log_visibility"),
    CheckConstraint(_in("ci_status", CI_STATUSES), name="ck_log_ci_status"),
)

checkmarks = Table(
    "checkmarks",
    metadata,
    # agent_id is PK *and* FK: "the small file that gets overwritten," one row per agent.
    Column("agent_id", BigInteger, ForeignKey("agents.id"), primary_key=True),
    Column("checkpoint_at", PortableTimestamp, nullable=False),
    Column("status", String, nullable=False),
    Column("where_it_stopped", String),
    Column("next_steps", PortableJSON),
    Column("open_question", String),
    # use_alter breaks the checkmarks <-> log_entries create-order cycle.
    Column(
        "log_entry_id",
        BigInteger,
        ForeignKey("log_entries.id", use_alter=True, name="fk_checkmarks_log_entry"),
    ),
    Column("tests_status", String, nullable=False, server_default="unknown"),
    Column("tested_at", PortableTimestamp),
    Column("build_status", String, nullable=False, server_default="unknown"),
    Column("built_at", PortableTimestamp),
    CheckConstraint(_in("status", AGENT_STATUSES), name="ck_checkmarks_status"),
    CheckConstraint(_in("tests_status", GATE_STATUSES), name="ck_checkmarks_tests"),
    CheckConstraint(_in("build_status", GATE_STATUSES), name="ck_checkmarks_build"),
)

shared_context = Table(
    "shared_context",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", String, nullable=False),
    Column("set_by_agent_id", BigInteger, ForeignKey("agents.id")),
    Column("updated_at", PortableTimestamp, nullable=False, server_default=func.now()),
)

# The record the hard approval gate checks (Phase 2). A senior agent writes one per
# branch it approves; the deploy gate refuses to merge/deploy a branch whose latest
# approval isn't ``approved`` and wasn't made by a *different* agent than the one pushing
# — so review is a genuine second context, never self-approval. ``approved_sha`` pins the
# approval to the reviewed commit so pushing new commits invalidates a stale approval.
approvals = Table(
    "approvals",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("project_id", String, ForeignKey("projects.id"), nullable=False),
    Column("branch", String, nullable=False),
    Column("approved_sha", String),  # the HEAD the reviewer signed off on, when known
    Column("pr_ref", String),  # optional forge PR number/URL, for traceability
    Column("status", String, nullable=False),
    # The reviewing agent, when an agent recorded the verdict. Nullable so an operator can
    # approve/reject from the dashboard (no acting agent) — such rows set ``actor`` instead.
    Column("approved_by_agent_id", BigInteger, ForeignKey("agents.id")),
    # Human-readable actor label for a non-agent verdict, e.g. "operator:web". The deploy
    # gate's "different agent than the pusher" check treats a null agent id as a genuine
    # second party, so operator approvals satisfy it.
    Column("actor", String),
    Column("note", String),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    CheckConstraint(_in("status", APPROVAL_STATUSES), name="ck_approvals_status"),
    Index("ix_approvals_project_branch", "project_id", "branch"),
)

# The control-action queue + audit log (README §"web management"). The API writes a
# ``queued`` row; the worker in the control container claims it (status -> ``running``),
# dispatches to the matching control function, and writes ``done``/``failed`` back with a
# result/error. ``project_id`` is nullable because poll_ci can sweep every project at once.
commands = Table(
    "commands",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("project_id", String, ForeignKey("projects.id")),
    Column("agent_name", String),  # target agent for spawn/kill/resume; null otherwise
    Column("type", String, nullable=False),
    Column("payload", PortableJSON),  # type-specific args (role/worktree/task, branch/sha…)
    Column("status", String, nullable=False, server_default="queued"),
    Column("result", PortableJSON),
    Column("error", String),
    Column("requested_by", String),  # actor label, e.g. "operator:web"
    Column("claimed_by", String),  # worker id that claimed the command
    # Pins a command to one worker (null = any). login_submit must run on the worker that
    # ran login_start — the live tmux login session exists only in that container.
    Column("target_worker", String),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    Column("claimed_at", PortableTimestamp),
    Column("finished_at", PortableTimestamp),
    CheckConstraint(_in("type", COMMAND_TYPES), name="ck_commands_type"),
    CheckConstraint(_in("status", COMMAND_STATUSES), name="ck_commands_status"),
    # The worker claims oldest-queued-first; this index serves that hot path.
    Index("ix_commands_status_id", "status", "id"),
)

# Web-managed git servers (README §"web management"). Makes the host->token-env mapping
# that ``control.credentials`` used to hardcode into an editable registry, and lets
# operators register self-hosted forges without a code change. The built-in map in
# ``control.credentials`` remains the fallback when a host has no row here.
#
# A server may also carry its own credentials, so projects need nothing per-repo:
# - ``token_enc``: the forge/git token, Fernet-encrypted (see ``handler.secretstore``) —
#   resolved for any project on this host with no ``credential_ref`` of its own, and
#   addressable explicitly as ``db:host:<hostname>``.
# - ``ssh_public_key`` / ``ssh_private_key_enc``: a per-server ed25519 deploy key. The
#   public half is shown in the dashboard to paste into the forge; the private half is
#   encrypted at rest and only ever materialized in the control container.
forge_hosts = Table(
    "forge_hosts",
    metadata,
    Column("hostname", String, primary_key=True),  # e.g. "github.com", "git.corp.internal"
    Column("forge_type", String, nullable=False),
    Column("token_env_var", String),  # per-host env name to inject, e.g. "GITHUB_TOKEN"
    Column("base_url", String),  # HTTPS base for the credential-helper scope, when non-default
    Column("token_enc", String),  # encrypted forge token; never returned by the API
    Column("ssh_public_key", String),  # OpenSSH public key, shown to the operator
    Column("ssh_private_key_enc", String),  # encrypted private key; never returned by the API
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    CheckConstraint(_in("forge_type", FORGE_TYPES), name="ck_forge_hosts_type"),
)

# Control-plane key/value secrets, Fernet-encrypted like forge_hosts tokens (see
# ``handler.secretstore``). Holds the claude OAuth credential bundle so every worker
# container can materialize it locally — the login flow runs on ONE worker, but all of
# them need to run ``claude``. Never exposed by any API route.
runtime_secrets = Table(
    "runtime_secrets",
    metadata,
    Column("key", String, primary_key=True),
    Column("value_enc", String, nullable=False),
    Column("updated_at", PortableTimestamp, nullable=False, server_default=func.now()),
)

# Worker registry + heartbeat (headless runner). Each worker container upserts its row
# every loop pass; the reaper marks a worker's running runs (and their agents) ``crashed``
# when ``heartbeat_at`` goes stale — the positive-liveness replacement for tmux scraping.
workers = Table(
    "workers",
    metadata,
    Column("id", String, primary_key=True),  # "worker-<host>-<pid>-<rand>"
    Column("hostname", String),
    Column("pid", BigInteger),
    Column("max_runs", BigInteger),
    Column("active_runs", BigInteger),
    Column("started_at", PortableTimestamp, nullable=False, server_default=func.now()),
    Column("heartbeat_at", PortableTimestamp, nullable=False, server_default=func.now()),
)

# One row per headless ``claude -p`` invocation. The spawn/resume *command* finishes at
# launch (fire-and-forget, matching tmux semantics); the run row is what tracks the
# process's actual life — status, exit code, and the final result event.
agent_runs = Table(
    "agent_runs",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("agent_id", BigInteger, ForeignKey("agents.id"), nullable=False),
    Column("session_id", String, nullable=False),
    Column("worker_id", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("status", String, nullable=False, server_default="running"),
    # Cross-worker kill: any worker/API sets this; the owning supervisor polls it and
    # SIGTERMs its own child — nobody signals a process they don't own.
    Column("cancel_requested", Boolean, nullable=False, server_default="0"),
    Column("exit_code", BigInteger),
    Column("result", PortableJSON),  # the stream's result event (cost/turns/is_error/text)
    Column("started_at", PortableTimestamp, nullable=False, server_default=func.now()),
    Column("finished_at", PortableTimestamp),
    CheckConstraint(_in("kind", RUN_KINDS), name="ck_agent_runs_kind"),
    CheckConstraint(_in("status", RUN_STATUSES), name="ck_agent_runs_status"),
    Index("ix_agent_runs_status_worker", "status", "worker_id"),
)

# The persisted event stream — one row per stream-json stdout line of a run, in order.
# This is what the UI's log/event panel reads; ``type`` mirrors the stream's top-level
# type (system/assistant/user/result), plus ``hook`` (--include-hook-events), ``worker``
# (runner-generated notices: crash marks, archive failures, fallback resumes) and ``raw``
# (an unparseable line, stored verbatim — the parser never drops data).
agent_events = Table(
    "agent_events",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("agent_id", BigInteger, ForeignKey("agents.id"), nullable=False),
    Column("run_id", BigInteger, ForeignKey("agent_runs.id"), nullable=False),
    Column("session_id", String),
    Column("seq", BigInteger, nullable=False),  # per-run stdout line counter
    Column("type", String, nullable=False),
    Column("payload", PortableJSON),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    Index("ix_agent_events_agent_id", "agent_id", "id"),
)

# Latest claude session archive per agent — the tar.gz of ``<sid>.jsonl`` + its sidecar
# dir from ``~/.claude/projects/<munged-cwd>/``. Uploaded by the supervising worker
# (periodically and at run end) and materialized by whichever worker claims the next
# resume, so ``--resume`` works cross-worker with no shared filesystem (README: DB is the
# single source of truth; observed sizes are KBs-to-low-MBs).
session_archives = Table(
    "session_archives",
    metadata,
    Column("agent_id", BigInteger, ForeignKey("agents.id"), primary_key=True),
    Column("session_id", String, nullable=False),
    Column("archive", LargeBinary, nullable=False),
    Column("bytes", BigInteger, nullable=False),
    Column("updated_at", PortableTimestamp, nullable=False, server_default=func.now()),
)

# ---- Claude management (web-managed). What the operator configures in the dashboard's
# Claude page; the control container applies it to every launch — skills sync to the
# worker's user-level ~/.claude/skills, connectors become the --mcp-config file, and
# plugins/permissions fold into the generated per-agent settings.json (settings_gen).
# Transports an MCP connector can use, mirroring claude's .mcp.json server types.
MCP_TRANSPORTS = ("stdio", "http", "sse")

# Operator-authored Claude Code skills (SKILL.md bodies). Distinct from the forge role
# skills (skills_gen), which are committed into managed repos; these are user-level and
# synced to every worker at launch.
claude_skills = Table(
    "claude_skills",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False, unique=True),  # slug; becomes the skill dirname
    Column("description", String),
    Column("content", String, nullable=False),  # markdown body below the front-matter
    Column("enabled", Boolean, nullable=False, server_default="1"),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    Column("updated_at", PortableTimestamp, nullable=False, server_default=func.now()),
)

# Auxiliary files belonging to a managed skill (references/, scripts/, …) — captured by
# the install-from-prompt import for skills that ship more than a SKILL.md, and synced
# alongside it. Paths are relative to the skill's directory; text content only.
claude_skill_files = Table(
    "claude_skill_files",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column(
        "skill_id",
        BigInteger,
        ForeignKey("claude_skills.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("path", String, nullable=False),
    Column("content", String, nullable=False),
    UniqueConstraint("skill_id", "path", name="uq_claude_skill_files_skill_path"),
)

# MCP servers ("connectors") agents may reach. Written per-launch as an --mcp-config
# file, so nothing lands in the managed repo's tree.
claude_connectors = Table(
    "claude_connectors",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False, unique=True),  # the mcpServers key
    Column("transport", String, nullable=False),
    Column("command", String),  # stdio: the executable
    Column("args", PortableJSON),  # stdio: argv list
    Column("env", PortableJSON),  # stdio: environment map
    Column("url", String),  # http/sse: the endpoint
    Column("headers", PortableJSON),  # http/sse: header map (may carry auth)
    Column("enabled", Boolean, nullable=False, server_default="1"),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    CheckConstraint(_in("transport", MCP_TRANSPORTS), name="ck_claude_connectors_transport"),
)

# Claude Code plugins, pinned to the marketplace that serves them. Folded into generated
# settings as extraKnownMarketplaces + enabledPlugins so headless runs auto-install them.
claude_plugins = Table(
    "claude_plugins",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),  # the plugin's name within its marketplace
    Column("marketplace", String, nullable=False),  # marketplace key, e.g. "acme-tools"
    Column("marketplace_repo", String, nullable=False),  # "owner/repo" or a git URL
    Column("enabled", Boolean, nullable=False, server_default="1"),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    UniqueConstraint("name", "marketplace", name="uq_claude_plugins_name_marketplace"),
)

# Small JSON key/value store for the remaining Claude management state; first key is
# "permissions" — the operator's defaultMode override and extra allow/deny/ask rules,
# merged over the env-configured baseline by settings_gen at launch.
claude_config = Table(
    "claude_config",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", PortableJSON, nullable=False),
    Column("updated_at", PortableTimestamp, nullable=False, server_default=func.now()),
)

# Recurring agent spawns. The worker checks for due rows on every loop pass and enqueues
# an ordinary ``spawn`` command per firing (so scheduled runs show up in the Activity
# audit trail like any other control action). Agent names must be unique per project, so
# each firing appends a UTC timestamp to ``name_prefix``.
schedules = Table(
    "schedules",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("project_id", String, ForeignKey("projects.id"), nullable=False),
    Column("name_prefix", String, nullable=False),  # runs are named <prefix>-<timestamp>
    Column("task", String, nullable=False),  # the prompt each run starts with
    Column("role", String),
    Column("worktree", String),  # optional branch for a per-run git worktree
    Column("subdir", String),  # optional subdir under the project root
    Column("interval_seconds", BigInteger, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("next_run_at", PortableTimestamp, nullable=False),
    Column("last_run_at", PortableTimestamp),
    Column("last_command_id", BigInteger, ForeignKey("commands.id")),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    Index("ix_schedules_enabled_next", "enabled", "next_run_at"),
)
