# handler

A remote control wrapper for [Claude Code](https://claude.com/claude-code) agents.
Run many `claude` agents across many projects — each isolated, each leaving behind a
**checkmark** (its current state) and an entry in a **big log** (the complete history) —
all backed by a centralized database, driven entirely through an HTTP API.

Every agent process is a real `claude` binary invocation. There is no hard dependency on
any particular git host or network layer: you bring your own Claude Code login, your own
git remote, and your own network exposure.

> **Status: Phase 1 MVP.** The control layer, HTTP API, database, migrations, and
> verification hooks are implemented and tested (45 tests, SQLite). Live end-to-end agent
> spawning against a real `claude` binary + tmux is stubbed behind mockable seams and
> wired but not yet exercised against production binaries. See
> [`docs/PLAN.md`](docs/PLAN.md) for the full design and roadmap.

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
| `WEBHOOK_URL` | Generic target for the `Notification` hook (ntfy, Slack, …) | unset → no-op |
| `PROJECTS_ROOT` | Base dir for per-project roots / worktrees | `./projects` |
| `CLAUDE_BIN` / `MISE_BIN` / `TMUX_BIN` | Binary overrides | `claude` / `mise` / `tmux` |

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

## Control CLI

The `handler` command manages agent processes (the write side):

```bash
handler spawn  --project leeworks-api --name api --worktree feature/auth --task "add login"
handler list   [--project leeworks-api]
handler attach --project leeworks-api --name api
handler kill   --project leeworks-api --name api
```

`spawn` refuses any project whose working directory has no `.mise.toml` with a
`[tasks.test]` task — the verification gate is a hard requirement, not a convention. It
resolves the working directory (a subdirectory or a fresh git worktree, always under the
project root), writes a per-agent `.claude/settings.json` wiring the hooks, and launches a
`tmux` session with the agent's identity and `DATABASE_URL` injected into its environment.

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
`HANDLER_PROJECT_ID`, `HANDLER_AGENT_NAME`, `DATABASE_URL`), since hook stdin doesn't
carry it; the wiring itself lives in the generated `settings.json`.

## Development

```bash
pytest          # 45 tests, entirely on SQLite — no live claude/tmux/mise needed
ruff check .    # lint
# or, via the project's own mise tasks:
mise run verify # lint + test
```

The suite drives every API route through FastAPI's `TestClient`, exercises all four hook
types, and runs a real `alembic upgrade head` per test so the migration path itself is
covered. Three seams — `control.tmux`, `hooks.verify`, and `control.spawn.resume` — are
the mock points that stand in for live `claude`/`tmux`/`mise`, and the drop-in points for
wiring them up for real.

## Project layout

```
src/handler/
  config.py            # env-driven settings, shared by every entrypoint
  db/                  # SQLAlchemy Core schema, engine, portable types, upsert, DAL
  api/                 # FastAPI app, auth deps, pydantic schemas, routes
  control/             # CLI, tmux/worktree/settings-gen seams, spawn orchestration
  hooks/               # Stop/SessionEnd, PreToolUse gate, Notification, verify seam
  migrations/          # Alembic env + versions
tests/                 # DB, API, hook, and control tests (SQLite)
docs/PLAN.md           # full design + phased roadmap (the original plan of action)
```

## Roadmap

Phase 1 (this MVP) is the control layer + API. Still ahead: **Phase 2** forge integration
and credential resolution (PRs/issues/CI status via `forge`, one interface across GitHub /
GitLab / Gitea / Forgejo / Bitbucket), **Phase 3** a web UI, **Phase 4** optional
observability, and **Phase 5** open-source release. Details and design rationale live in
[`docs/PLAN.md`](docs/PLAN.md).

## License

MIT.
