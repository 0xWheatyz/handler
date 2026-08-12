# Changelog

All notable changes to handler are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are the `v*` tags
the image workflows publish (plus `latest` from every push to `main`).

## [Unreleased]

### Added — the pi harness for local models ([#29](https://github.com/0xWheatyz/handler/pull/29))

- **`harness` on model backends** (`claude` | `pi`, default `claude`). A backend row can
  now run its agents through the lightweight [pi coding agent](https://github.com/badlogic/pi-mono)
  instead of the `claude` binary. pi speaks the OpenAI Completions API natively, so a
  bare local endpoint (vLLM, llama.cpp, Ollama) works **without** a LiteLLM /
  claude-code-router translation proxy — and the loop is far lighter for slow local
  token throughput. Selectable in the dashboard's Claude → Models form and via
  `POST /claude/models`.
- **Full gate parity on pi** via a bundled bridge extension (`pi_bridge.ts`, generated
  into a per-agent `PI_CODING_AGENT_DIR` under `~/.handler-pi/`, outside the repo tree).
  All gate logic stays in the same tested Python hooks:
  - Stop/completion gate (tests green + committed + pushed) re-prompts pi with blockers;
  - `git push` runs the test → image-build → protected-branch approval chain and denies
    on failure; `forge merge` / `mise run deploy` hit the approval gate;
  - questions defer through a new `ask_operator` tool into the normal answer/resume flow;
  - memory recall injects at session start; `memory_search/get/save/link` are registered
    as native pi tools (pi has no MCP) through `python -m handler.mcpserver --call`.
- **Web tools for agents**: `web_search` and `web_fetch` (`handler.webtool`), registered
  on pi-harness agents. Fetch is provider-free (HTML stripped to readable text,
  size-capped). Search resolves `SEARXNG_URL` → `BRAVE_SEARCH_API_KEY` → a zero-config
  DuckDuckGo fallback.
- **Full built-in tool surface on pi**: `read`, `write`, `edit`, `bash` plus `grep`,
  `find`, `ls` (off by default in stock pi) — 14 tools total including the handler set.
- **Skills + prompts on pi**: pi discovers the same web-managed `~/.claude/skills` sync
  and the repo's committed `.claude/skills` (forge role skills); handler conventions are
  appended to pi's system prompt; `AGENTS.md` / `CLAUDE.md` are read natively.
- **Cross-worker resume for pi sessions**: single-JSONL transcripts pre-assigned by
  handler, archived/materialized through the existing `session_archives` flow.
- `PI_BIN` binary override; `SEARXNG_URL` / `BRAVE_SEARCH_API_KEY` settings; a `fake_pi`
  test binary and 22 new tests (370 total).

### Changed

- **Control image**: Node bumped from NodeSource 20 to 22 (pi requires ≥ 22.19; Claude
  Code needs ≥ 18, unaffected) and `@earendil-works/pi-coding-agent` is baked in
  alongside the Claude Code CLI.
- `control.models` refactored: `resolve_model()` returns the row + decrypted key and
  `harness_of()` / `claude_env()` split harness selection from env building.
  `resolve_model_env()` keeps its signature (claude rows unchanged; pi rows return `{}`).
- Dashboard Models form gained the harness selector and a `pi harness` badge; docs
  (`docs/local-models.md`, README) describe both harnesses.

### Database

- Migration **`0015_model_harness`**: adds `claude_models.harness`
  (`NOT NULL DEFAULT 'claude'`). Purely additive — every existing backend row keeps its
  current behavior. Applied automatically by the API container on start (`RUN_MIGRATIONS`
  stays `false` on control, as before).

### Deployment notes (for this release's rollout)

Merging to `main` publishes both images (`docker.yml` → `ghcr.io/0xwheatyz/handler`,
`docker-control.yml` → `ghcr.io/0xwheatyz/handler/control`). To roll out:

1. **Pull both images and restart API before control** (compose already orders this):
   the API applies `0015_model_harness` on boot; the control worker only needs the new
   column to exist when a pi backend is first selected.
2. **The control image must be the new build** before spawning any pi-harness agent —
   it carries the `pi` binary and Node 22. Older control containers refuse cleanly
   (launch fails loudly, no silent fallback to the subscription).
3. **No env changes required.** Optional: `SEARXNG_URL` or `BRAVE_SEARCH_API_KEY` on the
   control container for a real `web_search` provider (unset = DuckDuckGo fallback);
   `PI_BIN` only if pi lives off PATH.
4. **Existing agents are untouched**: subscription and claude-harness agents launch
   exactly as before; running agents and their resumes are unaffected by the migration.
5. **Rollback**: reverting the images is safe — the `harness` column is ignored by old
   code. Only agents already pinned to a pi backend would fail to resume until the new
   control image returns (`alembic downgrade` would drop the column; not needed for an
   image-level rollback).
6. **Volume/layout invariants unchanged**: same `PROJECTS_ROOT`, same
   `HANDLER_SECRET_KEY` everywhere, no new shared filesystem. pi state lives under the
   worker's `$HOME` (`~/.handler-pi/`) and sessions ride the existing DB archive flow.

### Verification

- 370 tests green (SQLite, real `alembic upgrade head` per test), including the new
  `fake_pi` runner suite and mocked web-tool provider tests.
- The bridge was validated live against pi 0.84.1 with a stub OpenAI endpoint: memory
  injection, push-gate denial (including protected-branch approval), the stop-gate
  block loop, `ask_operator` pause/resume, and the 14-tool surface all ran end to end
  through the real hooks and database.

## Earlier work (pre-changelog)

Phases 1–2 plus the web dashboard, headless runner, credential store, schedules, model
backends, skill install-from-prompt, and the agent memory layer predate this changelog;
see `docs/PLAN.md` and the merged PR history for their details.
