# Local model backends (Qwen-Coder & friends)

Handler runs agents on locally-hosted models through a **model backend** row, and every
backend picks one of two **harnesses**:

| Harness | Binary | Endpoint it needs | When to pick it |
|---|---|---|---|
| `claude` (default) | Claude Code | **Anthropic Messages API** incl. tool use — put LiteLLM / claude-code-router in front of a local server | You want the exact Claude Code toolchain (MCP connectors, plugins, permission modes) |
| `pi` | [pi coding agent](https://github.com/badlogic/pi-mono) | **bare OpenAI-compatible** (`/v1/chat/completions`) — vLLM, llama.cpp, Ollama directly, no proxy | You want the lightest loop for slow local token throughput |

Both harnesses keep handler's contract intact: the same hooks (test/completion gate,
push gate, approval gate), the same checkmark/log streaming, the same memory layer, the
same skills, kill/resume, and schedules. The Claude subscription (no backend selected)
always launches `claude` — pi is only ever used when you point an agent at a backend row
that says so.

## The claude harness

Nothing about how an agent works changes: it is still the same `claude` binary with the
same generated `settings.json`, hooks, skills, MCP connectors, plugins, and permission
gates. The only thing the backend changes is the environment of that one agent's
process:

| Variable | From |
|---|---|
| `ANTHROPIC_BASE_URL` | the backend's `base_url` |
| `ANTHROPIC_AUTH_TOKEN` | the backend's stored API key (decrypted at launch; a placeholder when none is stored, so the subscription OAuth token is never sent to a local endpoint) |
| `ANTHROPIC_MODEL` | the backend's `model` |
| `ANTHROPIC_SMALL_FAST_MODEL` | `small_fast_model`, falling back to `model` |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` (skip sidecar calls a local endpoint won't serve; override via the row's env map) |

Register backends on the dashboard's **Claude → Models** tab (or `POST /claude/models`),
then pick one from the **Model** dropdown when spawning an agent — or on a **Schedule**,
so every fired run spawns on that backend. No selection = the
worker's logged-in Claude subscription, exactly as before. The agent is *pinned* to its
backend: resumes come back up on the same one, and deleting a backend makes resumes of
its agents fail loudly rather than silently falling back to the subscription.

## Why "tool calling not working" happens with Qwen-Coder

Claude Code speaks the **Anthropic Messages API** (`POST /v1/messages`): it sends tool
definitions in Anthropic's schema and expects structured `tool_use` content blocks back.
Local servers — Ollama, llama.cpp's `llama-server`, LM Studio, vLLM's default OpenAI
mode — speak the **OpenAI Chat Completions API** instead. Point `ANTHROPIC_BASE_URL` at
one of those and the request either 404s or, with a naive translator in between, the
model's tool calls come back as *plain text* (Qwen emits its own XML-ish
`<tool_call>` format) that Claude Code can't execute. That is the whole failure: the
model is fine, the dialect in the middle is wrong.

Two things must both be true:

1. **The endpoint must serve the Anthropic Messages API**, translating to whatever your
   server speaks.
2. **The inference server must parse the model's native tool-call format into
   structured tool calls** — for Qwen that means a Qwen-aware parser/template, not the
   default one.

## Working stacks

### Recommended: vLLM (Qwen tool parser) + LiteLLM (Anthropic translation)

vLLM parses Qwen's tool-call format natively when told to:

```bash
# Qwen3-Coder
vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --port 8000

# Qwen2.5-Coder uses the hermes parser instead:
#   --tool-call-parser hermes
```

LiteLLM in front exposes the Anthropic `/v1/messages` endpoint:

```yaml
# litellm-config.yaml
model_list:
  - model_name: qwen3-coder-30b
    litellm_params:
      model: hosted_vllm/Qwen/Qwen3-Coder-30B-A3B-Instruct
      api_base: http://127.0.0.1:8000/v1
general_settings:
  master_key: sk-local-anything
```

```bash
litellm --config litellm-config.yaml --port 4000
```

Then register the backend in Handler: base URL `http://<host>:4000`, model
`qwen3-coder-30b`, API key `sk-local-anything`.

### llama.cpp / Ollama

- `llama-server` needs `--jinja` (and, for Qwen, a chat template with tool support —
  recent official Qwen GGUFs ship one; older community quants often don't, which is
  another common source of "tools don't work").
- Ollama supports OpenAI-style tool calling for models whose Modelfile template declares
  it; check `ollama show <model> --template` mentions `.Tools` before blaming the proxy.
- Either way, they still only speak OpenAI-dialect — keep LiteLLM (use
  `ollama_chat/<model>`, not `ollama/<model>`, for tool support) or
  [claude-code-router](https://github.com/musistudio/claude-code-router) in front as
  the Anthropic translator.

## The pi harness

Set **Harness: pi** on the backend row (or `"harness": "pi"` via `POST /claude/models`)
and point `base_url` straight at the OpenAI-compatible endpoint — no LiteLLM, no
claude-code-router:

```bash
# vLLM with the Qwen tool parser is all you need:
vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --port 8000
```

Backend row: base URL `http://<host>:8000/v1`, model
`Qwen/Qwen3-Coder-30B-A3B-Instruct`, harness `pi`, API key optional (pi requires *some*
credential, so handler injects a placeholder when none is stored). The same
tool-parser/template caveats apply as ever — the model's tool calls must come back as
structured `tool_calls`, so use vLLM's parser flags, `--jinja` on `llama-server`, or an
Ollama model whose template declares `.Tools`.

### What the control layer generates

At every launch (spawn *and* resume) the backend row is materialized into a per-agent
`PI_CODING_AGENT_DIR` under `~/.handler-pi/` — outside the repo tree, so the clean-tree
completion gate never sees generated files:

- **`models.json` + `settings.json`** — the row as a pi provider (`openai-completions`
  by default) pinned as the default model. Row `env` keys `PI_PROVIDER_API`,
  `PI_CONTEXT_WINDOW`, and `PI_MAX_TOKENS` tune it; everything else in the env map
  passes through to the process.
- **`extensions/handler-bridge.ts`** — the bundled bridge extension that adapts pi's
  events to the same `python -m handler.hooks` contract claude uses. It also activates
  pi's full built-in tool set — `read`, `write`, `edit`, `bash`, plus `grep`, `find`,
  and `ls`, which pi leaves off by default — alongside the handler tools it registers. The gates are the
  *same tested Python code*: the Stop/completion gate re-prompts pi with the blockers,
  `git push` runs the test + image-build + protected-branch approval gates and denies on
  failure, and questions go through an `ask_operator` tool that pauses the agent for the
  normal answer/resume flow. Memory recall is injected at session start, and the memory
  tools (`memory_search/get/save/link`) are registered directly — pi has no MCP by
  design, so the bridge shells to `python -m handler.mcpserver --call <tool>` instead.
  The bridge also registers **`web_search` / `web_fetch`** (`python -m handler.webtool`):
  pi ships no web tools and claude's live server-side at Anthropic, so these are
  handler-owned — fetch is plain HTTP + HTML-to-text with no provider needed, and search
  resolves `SEARXNG_URL` → `BRAVE_SEARCH_API_KEY` → a zero-config DuckDuckGo fallback.
- **`APPEND_SYSTEM.md`** — the handler conventions (completion contract, ask_operator,
  memory usage) appended to pi's system prompt.

Skills work unchanged: pi implements the same SKILL.md standard as Claude Code, and the
generated `settings.json` points pi's discovery at the web-managed `~/.claude/skills`
sync plus the repo's committed `.claude/skills` (the forge role skills). pi also reads
`AGENTS.md` / `CLAUDE.md` context files natively.

Sessions are single JSONL files pre-assigned by handler (`--session <path>`), so
cross-worker resume works exactly like claude's: archived to the DB, materialized by
whichever worker claims the resume, continued by launching pi again on the same file.

### What differs from the claude harness

- **MCP connectors and plugins don't apply** — pi has no MCP client or plugin system.
  The bundled memory server and the web tools are bridged as native tools; other
  connectors are claude-harness-only for now.
- **Permission modes don't apply** — pi has no permission system. The hard gates
  (PreToolUse-equivalent blocking, Stop gate) are enforced by the bridge, which is the
  layer handler actually relies on for claude too.
- **`--max-budget-usd` doesn't apply** — local tokens are free; pi has no budget flag.
- The `pi` binary must be on the worker's PATH (the control image bakes it in;
  `PI_BIN` overrides, same as `CLAUDE_BIN`).

## Expectations and tips for small models

- **Keep the harness light.** Handler's agents run tool-heavy (hooks, MCP connectors,
  skills). A 7B model will fumble that loop; Qwen3-Coder-30B-class models handle it
  reasonably. Disable connectors the agent doesn't need and keep tasks small and
  concrete.
- **Raise timeouts, cap output.** The row's env map is the escape hatch:
  `API_TIMEOUT_MS=600000`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192` are sensible for a
  local 30B.
- **The gates don't relax.** The Stop/PreToolUse hooks still block un-tested,
  un-pushed work regardless of which model produced it — that's the point of keeping
  the same binary.
- **The subscription is untouched.** The web login, credential sync, and every agent
  spawned without a model selection keep working exactly as before; backends are purely
  additive.
