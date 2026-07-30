# Local model backends (Qwen-Coder & friends)

Handler can run agents on locally-hosted models without changing anything about how an
agent works: it is still the same `claude` binary with the same generated
`settings.json`, hooks, skills, MCP connectors, plugins, and permission gates. The only
thing a **model backend** changes is the environment of that one agent's process:

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
