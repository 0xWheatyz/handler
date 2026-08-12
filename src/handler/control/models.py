"""Model backends: run the same ``claude`` binary against a non-subscription endpoint.

An operator-registered ``claude_models`` row is an **Anthropic-API-compatible** endpoint
(a local Qwen/Llama behind LiteLLM or claude-code-router, an LLM gateway, …). Selecting
one at spawn doesn't change how an agent is launched at all — it is still ``claude -p``
with the same generated settings, hooks, skills, connectors, and gates. The only
difference is the environment this module builds: ``ANTHROPIC_BASE_URL`` points the
binary at the endpoint, ``ANTHROPIC_MODEL`` / ``ANTHROPIC_SMALL_FAST_MODEL`` name what
it serves, and ``ANTHROPIC_AUTH_TOKEN`` carries the endpoint's key (decrypted here, in
the control container, from the encrypted column — the API never returns it).

For the default ``harness='claude'`` the endpoint must speak the Anthropic Messages API
*including tool use*. A bare OpenAI-compatible server (Ollama, llama.cpp, LM Studio,
vLLM) is not enough on its own — that mismatch is exactly the "tool calling not working"
failure with Qwen-Coder — so put a translating proxy in front and enable the backend's
native tool parser; see ``docs/local-models.md`` for working stacks.

``harness='pi'`` rows skip all of that: the lightweight pi coding agent speaks the
OpenAI Completions API natively, so the row's ``base_url`` is the bare local endpoint
and there is no ``ANTHROPIC_*`` env at all — the row renders into a pi provider config
instead (see ``control.pi_harness``).
"""

from __future__ import annotations

from .. import secretstore
from ..db import repository as repo

# Injected when a backend stores no key: claude requires *some* credential once
# ANTHROPIC_BASE_URL is overridden, most local proxies accept anything, and falling
# through to the subscription OAuth token would send it to the local endpoint.
_PLACEHOLDER_KEY = "handler-local"

# Skip the sidecar calls a hobby-grade local endpoint won't implement; the main
# /v1/messages loop is unaffected. Overridable per-row via the ``env`` map.
_LOCAL_DEFAULTS = {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}


class ModelError(Exception):
    """Raised when a selected model backend cannot be resolved into an environment."""


def resolve_model(
    conn, model_id: int | None, *, require_enabled: bool = False
) -> tuple[dict, str] | None:
    """The backend row + its decrypted API key (a placeholder when none is stored), or
    ``None`` for ``model_id=None`` (the Claude subscription).

    ``require_enabled`` is the spawn path (a disabled backend must not take new agents);
    resumes pass False so an agent already pinned to a since-disabled backend can still
    finish its work. A deleted row always raises — resuming against nothing would
    silently fall back to the subscription, which is the one thing the operator asked
    this agent not to use.
    """
    if model_id is None:
        return None
    row = repo.get_claude_model(conn, model_id)
    if row is None:
        raise ModelError(
            f"model backend id={model_id} no longer exists; it was removed after this "
            "agent was spawned"
        )
    if require_enabled and not row["enabled"]:
        raise ModelError(f"model backend '{row['name']}' is disabled")
    if row.get("api_key_enc"):
        try:
            key = secretstore.decrypt(row["api_key_enc"])
        except secretstore.SecretStoreError as exc:
            raise ModelError(
                f"model backend '{row['name']}': cannot decrypt its API key — {exc}"
            ) from exc
    else:
        key = _PLACEHOLDER_KEY
    return row, key


def harness_of(resolved: tuple[dict, str] | None) -> str:
    """Which agent binary a resolved backend launches; the subscription is claude."""
    if resolved is None:
        return "claude"
    return resolved[0].get("harness") or "claude"


def claude_env(resolved: tuple[dict, str] | None) -> dict[str, str]:
    """The ``ANTHROPIC_*`` env for a claude-harness backend, ``{}`` for None (the
    subscription needs no overrides)."""
    if resolved is None:
        return {}
    row, key = resolved
    env = {
        **_LOCAL_DEFAULTS,
        "ANTHROPIC_BASE_URL": row["base_url"],
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_MODEL": row["model"],
        "ANTHROPIC_SMALL_FAST_MODEL": row.get("small_fast_model") or row["model"],
    }
    # Row-level extras win over everything — the operator's escape hatch for endpoint
    # quirks (API_TIMEOUT_MS, CLAUDE_CODE_MAX_OUTPUT_TOKENS, a different auth var, …).
    for k, v in (row.get("env") or {}).items():
        env[str(k)] = str(v)
    return env


def resolve_model_env(
    conn, model_id: int | None, *, require_enabled: bool = False
) -> dict[str, str]:
    """The claude-harness env overrides for ``model_id`` (``{}`` for the subscription).
    Kept as the validation seam ``spawn`` fail-fasts through; pi-harness rows resolve
    fine here too (spawn only checks resolvability), their env just isn't this one."""
    resolved = resolve_model(conn, model_id, require_enabled=require_enabled)
    if harness_of(resolved) != "claude":
        return {}
    return claude_env(resolved)
