# handler

# Remote Control Wrapper — Plan of Action

**Status:** Living document — update phase checkboxes and status in place as work completes. Don't append new copies of this file; overwrite it, the way a checkmark gets overwritten.
**Last updated:** 2026-07-07 (revision 7: accepted `forge`'s maturity as a risk worth taking — pin to a released version, fork/vendor if it ever stalls)

---

## 1. What "done" looks like

Production release means:

- **Runs anywhere.** No hard dependency on Gitea or Tailscale — git hosting and network exposure are both pluggable, not assumed.
- A **web UI**, not just tmux/CLI, for spawning, monitoring, and interacting with agents.
- **All communication goes through an API.** The UI is a client of it; tmux/CLI become optional local conveniences, not the source of truth.
- Every agent leaves a **checkmark** behind: a small, current-state record of where it stopped, what's needed next, and any open questions for you.
- Every checkmark links to an entry in a **big log**: the append-only, complete history of everything every agent has ever done.
- State lives in a **centralized database** that the CLI wrapper (backend) writes to and the API reads from — not scattered flat files or a git-hosting-specific store. Control layer and API containers hold nothing persistent themselves; they can restart, redeploy, or scale out without losing data because all of it lives in the database.
- **Multiple projects run concurrently, each isolated from the others by default.** One control layer can host any number of projects, each with its own agents, working directory, and history — with an explicit, opt-in mechanism for the edge cases where something genuinely needs to cross that boundary.

## 2. Non-negotiable constraints

- Every agent process is a real `claude` binary invocation. No OAuth handling, no protocol reimplementation.
- **No hard dependency on Tailscale.** The API authenticates itself with a bearer token; users choose their own network exposure — Tailscale, a VPN, a reverse proxy, or plain localhost. The wrapper doesn't assume any of them.
- **No hard dependency on Gitea.** Git operations use plain `git` by default. Forge-specific niceties (PRs, issues, CI status) go through `forge` (git-pkgs/forge) as an optional, pluggable layer — one CLI that works the same against GitHub, GitLab, Gitea/Forgejo, or Bitbucket, never a requirement just to run the tool.
- **The database never stores raw credentials.** `projects.credential_ref` is a pointer (an env var name, a file path, a command to run) — never a token. The control layer resolves it to an actual secret only at spawn time, injected into that container's environment for that run.
- Design decisions above a stakes threshold get surfaced via `plan` mode + `AskUserQuestion`, not silently guessed.
- **Projects are isolated by default.** An agent only sees its own project's working directory, checkmarks, and log — nothing crosses that boundary unless something is explicitly marked shared. This is one operator running many of their own projects, not a multi-tenant service for other people — don't let the isolation model drift into looking like the latter.
- **Agents don't get to self-report "done."** A verification gate actually runs the project's own test task and blocks completion on failure — "done" in the database means a test run passed, not that the agent stopped talking.
- **A `git push` doesn't leave until a local build check passes too.** Same hard-block pattern as the test gate, and it runs after tests, not instead of them — cheap checks run before the more expensive one that would obviously fail anyway.
- If this ships open-source: no embedded credentials, no implied Anthropic affiliation, README states plainly that each user brings their own Claude Code login, their own git remote, and their own network layer.

## 3. Control layer + API (build this first — this is the MVP)

### 3.1 Data model — Postgres primary, SQLite fallback

Two supported backends behind one data-access layer, not two separate code paths:

- **Postgres (default for real deployments).** A live, centralized server is what actually makes "stateless containers" true — the control layer and API are just compute that can restart, redeploy, or scale to N replicas because none of them hold state locally. This is the deployment target for anyone running more than a single node, or wanting one datastore behind multiple agent hosts.
- **SQLite (minimal-infra fallback).** A single file, zero services to stand up — for a single-node/homelab-scale run where standing up Postgres is overkill. Explicitly a fallback, not the default: it doesn't give you the centralization the Postgres path does, and single-writer semantics limit it to one control-layer instance at a time.

The schema is the same shape on both; only types differ slightly (Postgres gets proper `SERIAL`/`TIMESTAMPTZ`/`JSONB`, SQLite uses its looser dynamic typing). Pick one query layer/ORM that supports both dialects rather than hand-maintaining two schemas — see open questions.

```sql
-- Postgres
CREATE TABLE projects (
  id TEXT PRIMARY KEY,               -- slug, e.g. "leeworks-api"
  root_dir TEXT NOT NULL,
  git_remote TEXT,
  credential_ref TEXT,                -- pointer to a secret, e.g. "env:LEEWORKS_TOKEN" — never the token itself, see 3.7
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agents (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  name TEXT NOT NULL,                -- unique within a project, not globally
  working_dir TEXT NOT NULL,
  status TEXT NOT NULL,              -- working | paused_for_input | blocked | done
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, name)
);

CREATE TABLE checkmarks (
  agent_id BIGINT PRIMARY KEY REFERENCES agents(id),
  checkpoint_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,
  where_it_stopped TEXT,
  next_steps JSONB,
  open_question TEXT,
  log_entry_id BIGINT REFERENCES log_entries(id),
  tests_status TEXT NOT NULL DEFAULT 'unknown',  -- pass | fail | unknown — see 3.5
  tested_at TIMESTAMPTZ,
  build_status TEXT NOT NULL DEFAULT 'unknown',  -- pass | fail | unknown — see 3.6
  built_at TIMESTAMPTZ
);

CREATE TABLE log_entries (
  id BIGSERIAL PRIMARY KEY,
  agent_id BIGINT NOT NULL REFERENCES agents(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  session_id TEXT,
  status TEXT NOT NULL,
  summary TEXT,
  decisions TEXT,
  question TEXT,
  answer TEXT,                       -- filled in on resume; only field ever touched post-insert
  visibility TEXT NOT NULL DEFAULT 'project',  -- project | global — see 3.4
  push_sha TEXT,                     -- set if this checkpoint pushed; null if it didn't
  ci_status TEXT NOT NULL DEFAULT 'not_applicable',  -- not_applicable | pending | pass | fail — see 3.6
  ci_checked_at TIMESTAMPTZ
);
```

```sql
-- SQLite (minimal-infra fallback) — same shape, simpler types
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  root_dir TEXT NOT NULL,
  git_remote TEXT,
  credential_ref TEXT,
  created_at TEXT NOT NULL
);
-- agents / checkmarks / log_entries: identical columns, JSONB becomes TEXT,
-- BIGSERIAL becomes INTEGER PRIMARY KEY AUTOINCREMENT, TIMESTAMPTZ becomes TEXT.
```

`checkmarks` is a literal upsert (`INSERT ... ON CONFLICT DO UPDATE` / `INSERT OR REPLACE`) keyed by `agent_id` — the "small file that gets overwritten," just as a row instead of a file. `log_entries` is insert-only except for the one `answer` backfill on resume, which is the DB equivalent of "linked directly to this checkmark." Agent identity is now `(project_id, name)`, not a bare name — two projects can each have an agent called `api` without colliding.

### 3.2 Backend (CLI wrapper) — the only thing that writes

- Spawns/lists/attaches/kills agents within a project (tmux + `claude` binary, one working directory or git worktree per agent, nested under that project's root)
- Owns every write to the database: creates the agent row, upserts the checkmark, inserts log entries
- Hooked via `Stop`/`SessionEnd` (checkpoint), `PreToolUse` (defer `AskUserQuestion`), `Notification` (fires a generic webhook — the user points that at ntfy, Pushover, Slack, email, whatever; the wrapper doesn't pick for them)

### 3.3 API — the only thing that reads (plus writes the answer back)

- Thin HTTP layer over the same database (Postgres in centralized deployments, SQLite for minimal-infra): `GET /projects`, `POST /projects`, `GET /projects/:project/agents`, `POST /projects/:project/agents`, `GET /projects/:project/agents/:name/checkmark`, `GET /projects/:project/agents/:name/log`, `POST /projects/:project/agents/:name/answer`, `POST /projects/:project/agents/:name/resume`
- Auth: a generated bearer token checked on every request. No assumption about what network the request arrives over — Tailscale, a VPN, or a bare reverse proxy are all just transport underneath it.
- The UI (Phase 3) and any future integration are just clients of this — same contract as `curl`.

### 3.4 Multi-project isolation and cross-project sharing

Every agent belongs to exactly one project. Isolation is the default; sharing is a deliberate, visible act, never an accident.

**Isolation:**
- Filesystem: each project gets its own root directory; agents in that project work only within it (subdirectories or git worktrees underneath), never reaching into another project's tree.
- Naming: tmux sessions follow `project__agent`, matching the `(project_id, name)` uniqueness in the database — no cross-project collisions, and it's visually obvious which project a session belongs to from `tmux ls`.
- Config: git remote, credential reference, and any other per-project settings, live on the `projects` row — not global config — so projects can point at entirely different repos, hosts, or forges independently.
- API: every agent route is nested under `/projects/:project/...`. There's no endpoint that returns another project's data by accident.

**The explicit sharing mechanism, for the edge cases:**
- `log_entries.visibility` — defaults to `project`, can be set to `global` when an agent (or you) decides a specific checkpoint genuinely matters beyond its own project. A `GET /shared/log` endpoint surfaces only the entries marked `global`, across all projects — a deliberate opt-in feed, not a merged view of everything.
- `shared_context` table — a small key-value store for standing facts multiple projects need to reference (a shared staging URL, a schema version, a convention decision), independent of any single checkpoint:
  ```sql
  CREATE TABLE shared_context (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    set_by_agent_id BIGINT REFERENCES agents(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  ```
  Any agent can read it (`GET /shared/context`); writing (`PUT /shared/context/:key`) is the one place worth gating behind an explicit flag or higher-trust token, since it's the one table every project implicitly trusts.

Nothing here allows one project to read another project's checkmarks or private log entries directly — the only paths across the boundary are the two explicit ones above.

### 3.5 Toolchains and test verification

Environment reliability and result reliability are two different problems — solve both, don't conflate them.

**Environment: mise, not nix.** A single generic base image (mise + the `claude` binary + `git` + `gh`) with no baked-in language runtimes — one image for every project regardless of stack. Each project carries its own `.mise.toml`, pinning exact tool versions (Rust, Python, Node, whatever) and a lockfile committed to the repo for strict, reproducible installs. On container start, `mise install --non-interactive` reads that lockfile and materializes the project's exact toolchain — the container doesn't need to know or care what language it's about to run. Nix would get similar pinning with more ceremony and a heavier runtime; since Docker already provides OS-level isolation, mise's language-level pinning is the right amount of tool for this.

Every project defines a canonical task, regardless of stack:

```toml
[tasks.test]
description = "Run the test suite"
run = "pytest"   # or `cargo test`, `npm test`, whatever the project actually uses

[tasks.verify]
depends = ["lint", "test"]
```

**Result: a Stop hook, not self-reporting.** After each turn, a `Stop` hook runs `mise run test` (or `verify`) in the agent's working directory and checks the exit code. Nonzero → `decision: "block"`, with the failure output fed back to the agent, so the turn cannot end on a broken test suite. This is what "correct" actually rests on: it's the same command for every project because mise's task abstraction is the uniform interface, and it's enforced by the harness, not reported by the model.

The result feeds straight into the schema already in place: the hook sets `checkmarks.tests_status` and `tested_at` on every checkpoint, so `status = 'done'` in the database is only ever true alongside a passing test run — not a claim taken on faith.

### 3.6 Push gate and CI follow-through

Tests catch broken code; they don't catch a broken container. A Dockerfile with a stale `COPY` path passes `pytest` fine and then fails to build — worth catching locally, before it costs a CI run.

**Local build check — cheap, throwaway, no registry involved.** Since CI/CD (on its own, beefier runner) owns the real build-and-push, the local check only needs to prove the Dockerfile is sound: a `kaniko`/`buildah` build with no push target, output discarded. No Docker socket, no `--privileged`, nothing the agent's own sandbox needs elevated trust for — it's the same category of tool CI systems adopted specifically to avoid handing out real Docker-in-Docker access. This is `mise run build-image` alongside the existing `test` task, same interface, same project regardless of stack.

**Enforcement — same mechanism as tests, one step later.** A `PreToolUse` hook matching `Bash(git push*)` runs the verification chain (tests, then the throwaway build — cheap first, expensive second) and returns `permissionDecision: "deny"` on the first failure, with the reason surfaced to the agent. A push that's already known to fail CI doesn't leave. `checkmarks.build_status`/`built_at` record the result the same way `tests_status` does.

**CI is still the authoritative gate — the wrapper just closes the loop on it.** Once a push clears the local checks and actually goes out, whatever CI system the host runs (GitHub Actions, Gitea/Forgejo Actions, GitLab CI) does the real build-and-push on its own runner, same as today. The wrapper records `push_sha` and sets `ci_status = 'pending'` on that log entry, then a background poller in the control layer — not a hook, since this can take minutes — checks the run tied to that commit with `forge ci list` / `forge ci log <id>`. Same two commands regardless of which host the project is on; `forge` detects the forge type from the remote, so this isn't per-host integration work, just one poller calling one interface. Once the run resolves, the poller backfills `ci_status` and `ci_checked_at` on that same log entry — the DB equivalent of "recording why it did or didn't ultimately land," without ever exposing the wrapper to inbound webhook traffic.

### 3.7 Credentials: forge and git

Two things need to authenticate per project — the `forge` CLI (for PRs, issues, CI status) and `git` itself (for push/pull) — and the design goal is one secret servicing both, not two to manage.

**Resolution, not storage.** `projects.credential_ref` is a pointer (`env:VAR_NAME`, `file:/path`, `cmd:some command`), never the token itself — mirrors `forge`'s own `--token-cmd` pattern, just one level up. At spawn time, the control layer resolves the reference to an actual value and injects it into that agent's container environment only — nothing persisted in Postgres/SQLite, nothing baked into an image.

**One token, two consumers, where the host allows it.** `forge` reads the resolved token from the environment directly (`GITHUB_TOKEN`, `GITEA_TOKEN`, `FORGE_TOKEN`, per host) with zero extra config once it's injected. For git's own HTTPS auth, the wrapper writes a small credential-helper at container start that hands back that same value — most self-hosted forges (Gitea/Forgejo, GitLab) accept a PAT as the HTTP password, so one token covers both `forge pr create` and `git push` for a given project.

**SSH deploy keys as the per-project alternative.** Some operators won't want a single token holding both git-write and forge-API scope. Where that matters, a project can use an SSH deploy key for git transport and a separately-scoped, more limited token for `forge`'s PR/issue/CI operations — configured per project, not mandated globally, since this is a real preference split among self-hosters rather than a settled question.

## 4. Phased roadmap

### Phase 0 — Prerequisites
- [ ] `claude` binary installed and authenticated (per user)
- [ ] `git` installed; `forge` (git-pkgs/forge) optional
- [ ] `mise` installed in the base agent image; each project supplies its own `.mise.toml` with, at minimum, a `test` task
- [ ] A Postgres connection string (default target) — or nothing at all if running the SQLite fallback for a single-node/minimal-infra setup

### Phase 1 — Control layer + API (the MVP)
- [ ] Database schema + migrations for both backends, Postgres default / SQLite fallback, including `projects` and project-scoped agents (section 3.1)
- [ ] Control script: spawn/list/attach/kill, tmux + `claude` binary, one working dir/worktree per agent, namespaced by project — itself stateless, all state written straight to the database
- [ ] Hooks writing checkmark/log rows (`Stop`/`SessionEnd`, `PreToolUse` defer, `Notification` → generic webhook), all scoped to the owning project
- [ ] HTTP API over the same database, bearer-token auth, all agent routes nested under `/projects/:project/`
- [ ] Resume flow: API endpoint takes an answer, feeds it back via `claude --resume`
- [ ] Shared-context and shared-log endpoints for the explicit cross-project edge case (section 3.4)
- [ ] `Stop` hook verification gate: `mise install` on checkout, `mise run test` on every checkpoint, block completion on failure (section 3.5)
- [ ] `PreToolUse` hook on `git push*`: throwaway `kaniko`/`buildah` build (no registry) after tests pass, hard-deny the push on either failure (section 3.6)

**Definition of done:** run several projects side by side, each with its own agents, working directories, toolchain, and history, entirely through `curl` + a token, against either a live Postgres instance or the SQLite fallback — no Gitea, no Tailscale, no UI required, no state stored anywhere the control layer or API containers themselves live, nothing crosses a project boundary unless explicitly shared, no agent reaches `done` without a passing test run to show for it, and no push leaves that a local build already proved would fail.

### Phase 2 — Forge integration
- [ ] Repo-scoped actions via `forge`: branch creation, PR open, issue linking — one interface across GitHub/GitLab/Gitea/Forgejo/Bitbucket instead of a per-host integration
- [ ] Pin `forge` to a specific released version, not `@latest` — accepted risk given the project's youth, mitigated by not floating on a moving target
- [ ] Credential resolution (section 3.7): `credential_ref` → injected env var at spawn, shared by `forge` and git's credential helper
- [ ] Background poller reading back CI run results via `forge ci list` / `forge ci log`, backfilling `ci_status`/`ci_checked_at` on the log entry that recorded the push (section 3.6)

### Phase 3 — Production UI
- [ ] Web frontend, API-backed only (same contract as `curl`)
- [ ] Project switcher, agent list per project, live checkmark view, log history, "answer this question" form, plus a view for the shared/global feed

**Definition of done:** open a URL, see every agent's state, answer a paused question, no terminal required.

### Phase 4 — Observability (moved back, now optional)
- [ ] Prometheus metrics endpoint on the API (agent counts, pending questions, checkpoint rate)
- [ ] Grafana/Loki wiring documented as an optional add-on for self-hosters who already run that stack — not a dependency for anyone else

### Phase 5 — Open-source release
- [ ] Strip any remaining homelab-specific defaults into config
- [ ] README: bring-your-own Claude Code login, bring-your-own network, bring-your-own git host, bring-your-own credential source (env var, file, or command)
- [ ] Publish

## 5. Open questions

- Project name — still Cutout / Handler / Dead Drop / Backchannel / Umbra.
- API implementation language/framework — wants a good story for *both* Postgres and SQLite (a query layer or ORM that speaks both dialects) plus minimal runtime deps, given "portable" is still a hard requirement.
- Default webhook target for `Notification` — ship a zero-config adapter (ntfy needs no account) or leave it fully bring-your-own from day one?
- Reference deployment for Postgres — user-supplied external instance only, or does the repo also ship a docker-compose/StatefulSet example for people with nowhere else to put it? (Either way, Postgres is the one stateful component in the system — everything else stays a disposable container.)
- Who can write to `shared_context` — any agent by default, or does it need a higher-trust token than the per-project routes get?
- Per-project API tokens vs one global token — least-privilege argues for scoping tokens to a project, but this is single-operator, not multi-tenant, so a global token may just be simpler and sufficient.
- Pre-bake common toolchains into the base image (faster container start, bigger image) vs. always `mise install` on checkout against a cached, mounted data dir (smaller image, first-run latency) — worth benchmarking rather than guessing.
- Is a `test` task in `.mise.toml` a hard requirement (container refuses to run the agent without one) or a soft convention the Stop hook just skips if missing? Leaning hard requirement, since a silent skip defeats the point of the gate.
- `forge` also ships as a Go library, not just a CLI — if the API implementation language lands on Go, worth importing it directly instead of shelling out to a subprocess. Relevant input to the language question above, not a decision on its own.
- One token for both `forge` and git push vs. separate SSH deploy key + scoped API token per project — reasonable defaults differ by how much a given operator trusts a single credential with both git-write and forge-API scope.
- Polling cadence for the CI status backfill — fixed interval with backoff, or piggyback on the agent's own next checkpoint? A dedicated poller is simpler to reason about but is one more always-on process in an otherwise mostly-idle system.
