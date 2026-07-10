# handler

A remote control wrapper for [Claude Code](https://claude.com/claude-code) agents.
Run many `claude` agents across many projects — each isolated, each leaving behind a
**checkmark** (its current state) and an entry in a **big log** (the complete history) —
all backed by a centralized database, driven entirely through an HTTP API.

Every agent process is a real `claude` binary invocation. There is no hard dependency on
any particular git host or network layer: you bring your own Claude Code login, your own
git remote, and your own network exposure.

> **Status: Phase 2 (forge integration) implemented on top of the Phase 1 MVP.** The
> control layer, HTTP API, database, migrations, and verification/approval hooks are
> implemented and tested (106 tests, SQLite). Phase 2 adds credential resolution +
> injection, role-based forge-workflow skills, a hard approval gate, and a CI-status
> poller. Live end-to-end agent spawning against a real `claude` binary + tmux is stubbed
> behind mockable seams (`tmux`, `verify`, `forge`, `gitops`, `spawn.resume`) and wired
> but not yet exercised against production binaries. See [`docs/PLAN.md`](docs/PLAN.md)
> for the full design and roadmap.

---

## Why

One operator running several of their own projects wants to fan work out to background
Claude Code agents and keep a reliable, queryable picture of what each one is doing —
without babysitting a wall of tmux panes. `handler` gives every agent:

- **A checkmark** — one small, always-current row: where it stopped, what's next, any
  open question for you. Overwritten on every checkpoint, like a file you keep saving.
- **A big log** — the append-only history of everything every agent has ever done.
- **A verification gate** — an agent never reaches `done` on its own say-so. A `Stop`
  hook runs the project's own test task and blocks the turn on failure, so `done` in the
  database means *a test run passed*.
- **A push gate** — a `git push` doesn't leave until tests pass *and* a throwaway image
  build succeeds locally, so a push already known to fail CI never goes out.
- **Isolation** — each project has its own working directory, agents, history, and
  credentials; nothing crosses the boundary unless you explicitly share it.

## Architecture

Three components over one database. The database is the only thing that holds state, so
the control layer and API are disposable compute that can restart or scale out freely.

```
        writes                                        reads (+ answer backfill)
  ┌──────────────────┐        ┌──────────────┐        ┌──────────────────┐
  │  control layer   │───────▶│   database   │◀───────│    HTTP API      │
  │  (CLI + hooks)   │        │  PG / SQLite │        │  (FastAPI)       │
  └──────────────────┘        └──────────────┘        └──────────────────┘
     │        ▲                                              ▲
     │ spawns │ Stop / PreToolUse / Notification hooks       │ curl, UI, any client
     ▼        │ write checkmark + log rows                   │ (bearer token)
  tmux + claude binary (one working dir / worktree per agent)
```

- **Control layer** (`handler.control`) — the only writer. Spawns/lists/attaches/kills
  agents as `tmux` sessions running the `claude` binary, one working directory or git
  worktree per agent, namespaced `project__agent`. Stateless; every write goes straight
  to the database.
- **Hooks** (`handler.hooks`) — run inside each agent via a generated `settings.json`.
  They write the checkpoint/log rows and enforce the test and push gates.
- **API** (`handler.api`) — a thin, read-mostly HTTP layer over the same database (the
  one write it does is backfilling an operator's answer). Bearer-token auth on every
  route; every agent route is nested under `/projects/:project/` so nothing leaks across
  a project boundary.

### One schema, two backends

The data model is defined once (SQLAlchemy Core) and renders correctly on both:

- **Postgres** (default for real deployments) — `BIGSERIAL`, `TIMESTAMPTZ`, `JSONB`.
  A live central server is what makes the stateless-container story true.
- **SQLite** (minimal-infra fallback) — a single file, zero services. Same schema shape,
  simpler types (`INTEGER PRIMARY KEY`, TEXT, JSON).

Portable column types bridge the two, and the checkmark upsert uses native
`INSERT … ON CONFLICT DO UPDATE` on both dialects. Migrations are Alembic, dual-dialect.

## Requirements

- Python 3.11+
- `git` and `tmux` (for live spawning)
- A `claude` binary, authenticated (for live spawning)
- `mise` in each managed project, with a `.mise.toml` defining at least a `test` task
- Postgres (default) — or nothing but a file path for the SQLite fallback

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure

Configuration is entirely environment-driven (see [`.env.example`](.env.example)):

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | `sqlite:////abs/path.db` or `postgresql+psycopg://…` | `sqlite:///./handler.db` |
| `AUTH_TOKEN` | Global bearer token gating every API route | *(required for the API)* |
| `SHARED_CONTEXT_WRITE_TOKEN` | Higher-trust token gating `PUT /shared/context/:key` | falls back to `AUTH_TOKEN` |
| `ADMIN_TOKEN` | Gates the web control surface (enqueue commands, project/host CRUD, credential edits) | falls back to `AUTH_TOKEN` |
| `WEBHOOK_URL` | Generic target for the `Notification` hook (ntfy, Slack, …) | unset → no-op |
| `PROJECTS_ROOT` | Base dir for per-project roots / worktrees | `./projects` |
| `CLAUDE_BIN` / `MISE_BIN` / `TMUX_BIN` / `FORGE_BIN` / `GIT_BIN` | Binary overrides | `claude` / `mise` / `tmux` / `forge` / `git` |
| `FORGE_VERSION` | Pinned forge version verified at spawn (Phase 2) | unset → skip check |
| `PROTECTED_BRANCHES` | Branches a direct push needs an approval to reach (Phase 2) | `main,master` |

## Run

Apply migrations, then start the API:

```bash
export DATABASE_URL="sqlite:///$PWD/handler.db"
export AUTH_TOKEN="$(openssl rand -hex 32)"

alembic upgrade head
uvicorn handler.api.app:app --host 0.0.0.0 --port 8000
```

The API is just a client contract — everything below works with plain `curl`:

```bash
TOKEN="Authorization: Bearer $AUTH_TOKEN"
BASE="http://127.0.0.1:8000"

# Register a project and an agent
curl -s -X POST $BASE/projects -H "$TOKEN" -H 'Content-Type: application/json' \
  -d '{"id":"leeworks-api","root_dir":"/srv/projects/leeworks"}'

curl -s -X POST $BASE/projects/leeworks-api/agents -H "$TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"api","working_dir":"/srv/projects/leeworks/api"}'

# Read an agent's checkmark and log
curl -s $BASE/projects/leeworks-api/agents/api/checkmark -H "$TOKEN"
curl -s $BASE/projects/leeworks-api/agents/api/log -H "$TOKEN"

# Answer a paused question, then resume the agent
curl -s -X POST $BASE/projects/leeworks-api/agents/api/answer -H "$TOKEN" \
  -H 'Content-Type: application/json' -d '{"answer":"use Postgres"}'
curl -s -X POST $BASE/projects/leeworks-api/agents/api/resume -H "$TOKEN" \
  -H 'Content-Type: application/json' -d '{}'
```

## Containers

Two images are published to GHCR, one per process, sharing the package, the database, and
the `/var/lib/handler` data volume:

| Image | Dockerfile | Runs | Workflow |
|---|---|---|---|
| `ghcr.io/0xwheatyz/handler` | [`Dockerfile`](Dockerfile) | the API (`uvicorn`) — also applies migrations on start | [`docker.yml`](.github/workflows/docker.yml) |
| `ghcr.io/0xwheatyz/handler/control` | [`Dockerfile.control`](Dockerfile.control) | the control worker (`handler worker`) | [`docker-control.yml`](.github/workflows/docker-control.yml) |

The control image bakes in `git` + `tmux`; the `claude` and `forge` binaries are
bring-your-own (layer or mount them in for live agent spawning — the CI poller degrades
gracefully without `forge`). The **worker** drains the control-command queue the API
enqueues (spawn/kill/resume/approve/reject/forge-init/poll-ci) and sweeps CI on an interval
(subsuming `poll-ci --watch`), so the whole system is drivable from the dashboard — see
[Web management](#web-management).

[`docker-compose.yml`](docker-compose.yml) wires both up with Postgres. The API owns
migrations, so the control service runs with `RUN_MIGRATIONS=false` and waits for the API:

```bash
export AUTH_TOKEN="$(openssl rand -hex 32)"
export ADMIN_TOKEN="$(openssl rand -hex 32)"   # unlocks management actions in the dashboard
docker compose up -d                           # db + api + control (worker)

# One-shot control commands run against the same image:
docker compose run --rm control handler list
docker compose run --rm control handler spawn --project leeworks-api --name junior --task "…"
```

## Web management

The dashboard (and the API under it) manages everything — git credentials & hosts,
projects, agents, and approvals — without dropping to the CLI. Because the API and control
layer are **separate containers** (the API has no `git`/`tmux`/`claude` and doesn't own the
tmux sessions), the API can't run control actions directly. Instead it **enqueues a command**
and the worker in the control container executes it and writes the result back:

```
 Dashboard ──HTTP──▶ API (read + enqueue)              Control container
                        │  writes a `commands` row         │  worker: claim → dispatch → result
                        ▼                                   ▼
                     ┌─────────────── shared database ───────────────┐
                     │ projects  agents  approvals  commands  hosts  │
                     └────────────────────────────────────────────────┘
```

What the dashboard can now do (all state-changing actions require `ADMIN_TOKEN`):

- **Projects** — create / edit / delete (`root_dir`, `git_remote`, `credential_ref`).
- **Agents** — spawn (name, role, worktree/subdir, task) and kill via the queue; delete the
  row; plus the existing checkmark / log / answer-resume views.
- **Approvals** — record an operator verdict per branch (approve/reject); the deploy gate
  treats an operator verdict as a genuine second party (no self-approval).
- **Forge hosts** — a registry mapping a host to the token env var to inject at spawn, so
  self-hosted forges work without a code change (the built-in host map is the fallback).
- **Credentials** — manage a project's `credential_ref` **pointer**. The DB still never
  stores a raw token: web-settable schemes are `env:` / `file:` / `db:` (the `cmd:` scheme
  is CLI-only, since it would run an arbitrary command in the control container). `db:` is
  reserved for a future encrypted secret store.
- **Activity** — every enqueued command with its status (queued → running → done/failed) —
  the audit log of what the dashboard triggered. The UI polls `GET /commands/{id}` for
  live status.

The command queue is exposed over HTTP as `POST …/agents/spawn`, `POST …/agents/{n}/kill`,
`POST …/approvals`, `POST …/forge-init`, `POST …/poll-ci`, and `GET /commands[/{id}]`;
hosts as `/hosts`; project mutation as `PATCH`/`DELETE /projects/{id}`. Run the worker with
`handler worker` (the control image's default command).

## Control CLI

The `handler` command manages agent processes directly (an alternative to the queue, for
operators at a shell):

```bash
handler spawn  --project leeworks-api --name junior --role junior --worktree feat/auth --task "add login"
handler list   [--project leeworks-api]
handler attach --project leeworks-api --name junior
handler kill   --project leeworks-api --name junior

# Phase 2 — forge workflow
handler forge-init --project leeworks-api          # write + commit the role skills
handler approve --branch feat/auth --pr 12          # senior agent records its verdict
handler reject  --branch feat/auth --note "fix X"   # (project/agent from env in-session)
handler poll-ci [--project leeworks-api] [--watch]  # backfill CI verdicts
```

`spawn` refuses any project whose working directory has no `.mise.toml` with a
`[tasks.test]` task — the verification gate is a hard requirement, not a convention — and
it also refuses to start if the project's `credential_ref` is configured but can't be
resolved, so a broken secret pointer fails fast instead of leaving an orphaned agent. It
resolves the working directory (a subdirectory or a fresh git worktree, always under the
project root), writes a per-agent `.claude/settings.json` wiring the hooks, resolves and
injects the project's credentials (see below), and launches a `tmux` session with the
agent's identity and `DATABASE_URL` injected into its environment. `--role`
(`junior`/`senior`/`deploy`) records which forge-workflow role the agent plays.

## API reference

All routes require `Authorization: Bearer <AUTH_TOKEN>`. `GET /health` is unauthenticated.

| Method & path | Purpose |
|---|---|
| `GET /projects` · `POST /projects` | List / register projects |
| `GET /projects/:p/agents` · `POST …` | List / register agents (project-scoped) |
| `GET /projects/:p/agents/:name/checkmark` | The agent's current-state checkmark |
| `GET /projects/:p/agents/:name/log` | The agent's log history (paginated) |
| `POST /projects/:p/agents/:name/answer` | Backfill the operator's answer to an open question |
| `POST /projects/:p/agents/:name/resume` | Feed the answer back via `claude --resume` |
| `GET /shared/log` | Cross-project feed of entries explicitly marked `global` |
| `GET /shared/context` · `GET /shared/context/:key` | Read shared key/value facts |
| `PUT /shared/context/:key` | Write a shared fact — requires the shared-write token |

## Hooks

Wired into each agent as `python -m handler.hooks <event>`:

- **`Stop` / `SessionEnd`** — checkpoint. On `Stop`, run `mise run test`; on failure,
  return `decision: "block"` with the output so the turn cannot end on red. Records
  `tests_status` / `tested_at`; `status = 'done'` only ever accompanies a pass.
- **`PreToolUse`** — two jobs. An `AskUserQuestion` is *deferred*: the question is
  persisted, the checkmark set to `paused_for_input`, and the tool call denied so control
  hands off to the async answer/resume flow. A `Bash` command running `git push` triggers
  the push gate — tests first, then a throwaway image build (`mise run build-image`) — and
  is denied on the first failure.
- **`Notification`** — POSTs a small JSON payload to `WEBHOOK_URL` (no-op when unset).
  Never blocks the agent on delivery failure.

Hook identity travels via environment variables injected at spawn (`HANDLER_AGENT_ID`,
`HANDLER_PROJECT_ID`, `HANDLER_AGENT_NAME`, `HANDLER_AGENT_ROLE`, `DATABASE_URL`), since
hook stdin doesn't carry it; the wiring itself lives in the generated `settings.json`.

## Forge workflow (Phase 2)

Handler doesn't give the operator forge commands. It **configures forge for the agents**
and lets them drive a role-based dev workflow themselves — the operator only sets a
project's `credential_ref` (and optionally a `FORGE_VERSION` pin).

- **Three roles, three agents.** A `junior` agent writes the change and opens a PR; a
  `senior` agent reviews it and records an approval; a `deploy` agent merges and ships it.
  Each is a separate agent with its own tmux session and working dir, so review is a
  genuine second context — not the author signing off on their own work.
- **Skills, committed into the repo.** `handler forge-init` writes role skills
  (`forge-junior`, `forge-senior`, `forge-deploy`, plus an overview) into the managed
  repo's `.claude/skills/` and commits them, so the workflow travels with the code and is
  visible to humans. `forge` itself is already authenticated inside each agent, so it
  works the same across GitHub/GitLab/Gitea/Forgejo/Bitbucket.
- **A hard approval gate.** A merge or deploy command (`forge … merge`, `mise run deploy`)
  — and a direct `git push` to a protected branch (`main`/`master`, see `PROTECTED_BRANCHES`)
  — is *denied* unless a standing `approved` record exists for the current branch, made by
  a **different** agent than the one merging, and still pinned to the reviewed commit
  (pushing new commits invalidates a stale approval). Same block-on-failure mechanism as
  the test and push gates — the senior's `handler approve` is what unlocks it, no agent can
  approve its own branch, and the protected-branch rule closes the "merge locally, push to
  main" path around it.
- **CI follow-through.** When a push clears the local gates, Handler records the commit
  with `ci_status = 'pending'`. The `handler poll-ci` poller then asks `forge ci list` for
  the runs tied to that commit and backfills the authoritative verdict — one interface,
  any forge, no inbound webhook.

### Credentials — resolution, not storage (README 3.7)

The database never stores a raw token. A project's `credential_ref` is a **pointer**:

| Form | Meaning |
|---|---|
| `env:VAR_NAME` | read the value from an environment variable |
| `file:/path` | read (and strip) the value from a file |
| `cmd:some command` | run the command; its stdout is the value |

At spawn the control layer resolves the pointer and injects the value into that one
agent's environment as `FORGE_TOKEN` (plus the host-specific `GITHUB_TOKEN` /
`GITEA_TOKEN` / … when the remote is recognized). A repo-local git credential helper is
installed that hands the same value back for HTTPS push/pull — so one secret services both
`forge` and `git`, and the raw token lives only in the process environment, never on disk
or in the database.

## Development

```bash
pytest          # 106 tests, entirely on SQLite — no live claude/tmux/mise/forge/git needed
ruff check .    # lint
# or, via the project's own mise tasks:
mise run verify # lint + test
```

The suite drives every API route through FastAPI's `TestClient`, exercises all four hook
types plus the approval gate, credential resolution, the skills generator, and the CI
poller, and runs a real `alembic upgrade head` per test so the migration path itself is
covered. The seams — `control.tmux`, `control.forge`, `control.gitops`, `hooks.verify`,
and `control.spawn.resume` — are the mock points that stand in for live
`claude`/`tmux`/`mise`/`forge`/`git`, and the drop-in points for wiring them up for real.

## Project layout

```
src/handler/
  config.py            # env-driven settings, shared by every entrypoint
  db/                  # SQLAlchemy Core schema, engine, portable types, upsert, DAL
  api/                 # FastAPI app, auth deps, pydantic schemas, routes
  control/             # CLI, tmux/worktree/settings-gen seams, spawn orchestration,
                       # forge/gitops seams, credentials, skills_gen, CI poller
  hooks/               # Stop/SessionEnd, PreToolUse gate (push + approval), Notification
  migrations/          # Alembic env + versions
tests/                 # DB, API, hook, and control tests (SQLite)
docs/PLAN.md           # full design + phased roadmap (the original plan of action)
```

## Roadmap

Phase 1 (the MVP) is the control layer + API. **Phase 2** (forge integration) is
implemented: credential resolution + injection, role-based forge-workflow skills, the hard
approval gate, and the CI-status poller — one interface across GitHub / GitLab / Gitea /
Forgejo / Bitbucket. Still ahead: **Phase 3** a web UI, **Phase 4** optional observability,
and **Phase 5** open-source release. Details and design rationale live in
[`docs/PLAN.md`](docs/PLAN.md).

## License

MIT.
