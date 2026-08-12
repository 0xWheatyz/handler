"""Claude management: skills, MCP connectors, plugins, and permission overrides.

The dashboard's Claude page edits these rows directly — no worker round-trip, because
nothing here touches a live process. The control container reads the same tables at
every launch: skills sync to the worker's user-level ``~/.claude/skills``, connectors
become the run's ``--mcp-config`` file, and plugins/permissions fold into the generated
per-agent ``settings.json`` (``control.settings_gen`` / ``control.claude_gen``). Changes
therefore apply to the *next* launch of every agent, not to runs already in flight.

Skills, connectors, plugins, and model backends are per-user resources: everyone sees
the **shared** rows (owner NULL, admin-managed) plus their own, users create and manage
their own rows, and only what's visible to a project's owner is applied to its agents'
launches. Permission overrides stay global and admin-gated. The login flow stays under
``/login`` — it needs the worker's tmux.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection

from ... import secretstore
from ...config import get_settings
from ...db import repository as repo
from ..deps import Actor, db_conn, get_actor, require_admin, require_auth
from ..schemas import (
    ClaudeConnectorIn,
    ClaudeConnectorOut,
    ClaudeConnectorUpdateIn,
    ClaudeModelIn,
    ClaudeModelOut,
    ClaudeModelUpdateIn,
    ClaudePermissionsIn,
    ClaudePermissionsOut,
    ClaudePluginIn,
    ClaudePluginOut,
    ClaudePluginUpdateIn,
    ClaudeSkillIn,
    ClaudeSkillOut,
    ClaudeSkillUpdateIn,
    CommandOut,
    SkillInstallIn,
)

router = APIRouter(prefix="/claude", tags=["claude"], dependencies=[Depends(require_auth)])


def _require_create(actor: Actor) -> None:
    """Creating rows: users always may (they own what they create); legacy tokens keep
    their historical rule — only the admin token writes here."""
    if actor.kind == "token" and not actor.is_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="this action requires an admin token"
        )


def _require_edit(actor: Actor, row: dict, what: str) -> None:
    """Mutating a row: the owner or an admin. Shared rows (owner NULL) are admin-managed."""
    if not actor.can_edit(row.get("owner_user_id")):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"this {what} is shared — only an admin can change it"
            if row.get("owner_user_id") is None
            else f"this {what} belongs to another user",
        )


# ---- skills ---------------------------------------------------------------------------


def _skill_or_404(conn: Connection, skill_id: int, actor: Actor) -> dict:
    skill = repo.get_claude_skill(conn, skill_id)
    if skill is None or not actor.can_view(skill.get("owner_user_id")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"skill {skill_id} not found")
    return skill


def _skill_out(conn: Connection, row: dict) -> dict:
    """A skill row shaped for responses: auxiliary file *paths* attached (content stays
    server-side — it syncs to workers, the UI only lists what ships)."""
    files = repo.list_claude_skill_files(conn, row["id"])
    return {**row, "files": [f["path"] for f in files]}


@router.get("/skills", response_model=list[ClaudeSkillOut])
def list_skills(
    actor: Actor = Depends(get_actor), conn: Connection = Depends(db_conn)
) -> list[dict]:
    return [
        _skill_out(conn, s)
        for s in repo.list_claude_skills(conn, visible_to=actor.visible_scope)
    ]


@router.post(
    "/skills",
    response_model=ClaudeSkillOut,
    status_code=status.HTTP_201_CREATED,
)
def create_skill(
    body: ClaudeSkillIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    _require_create(actor)
    if repo.get_claude_skill_by_name(conn, body.name) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"skill '{body.name}' exists")
    return repo.create_claude_skill(
        conn,
        body.name,
        body.content,
        description=body.description,
        enabled=body.enabled,
        owner_user_id=actor.user_id,
    )


@router.post(
    "/skills/install",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_skill_install(
    body: SkillInstallIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    """Run a pasted marketplace install prompt on the worker (which has ``claude`` and
    network) and import what it fetches as managed skills. The UI polls the returned
    command like any other control action; its result carries the imported skill names
    and claude's report of the defaults it chose. Imported skills belong to the
    requesting user (shared when requested with the admin token)."""
    _require_create(actor)
    return repo.enqueue_command(
        conn,
        "skill_install",
        payload={"prompt": body.prompt, "owner_user_id": actor.user_id},
        requested_by=actor.label,
    )


@router.patch("/skills/{skill_id}", response_model=ClaudeSkillOut)
def update_skill(
    skill_id: int,
    body: ClaudeSkillUpdateIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    _require_edit(actor, _skill_or_404(conn, skill_id, actor), "skill")
    fields = body.model_dump(exclude_unset=True)
    if "name" in fields:
        clash = repo.get_claude_skill_by_name(conn, fields["name"])
        if clash is not None and clash["id"] != skill_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"skill '{fields['name']}' exists"
            )
    return _skill_out(conn, repo.update_claude_skill(conn, skill_id, **fields))


@router.delete("/skills/{skill_id}")
def delete_skill(
    skill_id: int,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    skill = _skill_or_404(conn, skill_id, actor)
    _require_edit(actor, skill, "skill")
    repo.delete_claude_skill(conn, skill_id)
    return {"deleted": skill["name"]}


# ---- connectors (MCP servers) ---------------------------------------------------------


def _connector_or_404(conn: Connection, connector_id: int, actor: Actor) -> dict:
    connector = repo.get_claude_connector(conn, connector_id)
    if connector is None or not actor.can_view(connector.get("owner_user_id")):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"connector {connector_id} not found"
        )
    return connector


@router.get("/connectors", response_model=list[ClaudeConnectorOut])
def list_connectors(
    actor: Actor = Depends(get_actor), conn: Connection = Depends(db_conn)
) -> list[dict]:
    return repo.list_claude_connectors(conn, visible_to=actor.visible_scope)


@router.post(
    "/connectors",
    response_model=ClaudeConnectorOut,
    status_code=status.HTTP_201_CREATED,
)
def create_connector(
    body: ClaudeConnectorIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    _require_create(actor)
    if repo.get_claude_connector_by_name(conn, body.name) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"connector '{body.name}' exists")
    return repo.create_claude_connector(
        conn,
        body.name,
        body.transport,
        command=body.command,
        args=body.args,
        env=body.env,
        url=body.url,
        headers=body.headers,
        enabled=body.enabled,
        owner_user_id=actor.user_id,
    )


@router.patch(
    "/connectors/{connector_id}",
    response_model=ClaudeConnectorOut,
)
def update_connector(
    connector_id: int,
    body: ClaudeConnectorUpdateIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    current = _connector_or_404(conn, connector_id, actor)
    _require_edit(actor, current, "connector")
    fields = body.model_dump(exclude_unset=True)
    if "name" in fields:
        clash = repo.get_claude_connector_by_name(conn, fields["name"])
        if clash is not None and clash["id"] != connector_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"connector '{fields['name']}' exists"
            )
    # Re-check the transport/field pairing against the merged row, so a PATCH can't
    # produce a stdio connector without a command or an http one without a url.
    merged = {**current, **fields}
    if merged["transport"] == "stdio":
        if not (merged.get("command") or "").strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="a stdio connector needs a command"
            )
    elif not (merged.get("url") or "").strip().startswith(("http://", "https://")):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"an {merged['transport']} connector needs an http(s) url",
        )
    return repo.update_claude_connector(conn, connector_id, **fields)


@router.delete("/connectors/{connector_id}")
def delete_connector(
    connector_id: int,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    connector = _connector_or_404(conn, connector_id, actor)
    _require_edit(actor, connector, "connector")
    repo.delete_claude_connector(conn, connector_id)
    return {"deleted": connector["name"]}


# ---- plugins --------------------------------------------------------------------------


def _plugin_or_404(conn: Connection, plugin_id: int, actor: Actor) -> dict:
    plugin = repo.get_claude_plugin(conn, plugin_id)
    if plugin is None or not actor.can_view(plugin.get("owner_user_id")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"plugin {plugin_id} not found")
    return plugin


@router.get("/plugins", response_model=list[ClaudePluginOut])
def list_plugins(
    actor: Actor = Depends(get_actor), conn: Connection = Depends(db_conn)
) -> list[dict]:
    return repo.list_claude_plugins(conn, visible_to=actor.visible_scope)


@router.post(
    "/plugins",
    response_model=ClaudePluginOut,
    status_code=status.HTTP_201_CREATED,
)
def create_plugin(
    body: ClaudePluginIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    _require_create(actor)
    if repo.get_claude_plugin_by_key(conn, body.name, body.marketplace) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"plugin '{body.name}@{body.marketplace}' exists",
        )
    return repo.create_claude_plugin(
        conn,
        body.name,
        body.marketplace,
        body.marketplace_repo,
        enabled=body.enabled,
        owner_user_id=actor.user_id,
    )


@router.patch("/plugins/{plugin_id}", response_model=ClaudePluginOut)
def update_plugin(
    plugin_id: int,
    body: ClaudePluginUpdateIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    current = _plugin_or_404(conn, plugin_id, actor)
    _require_edit(actor, current, "plugin")
    fields = body.model_dump(exclude_unset=True)
    if "name" in fields or "marketplace" in fields:
        merged = {**current, **fields}
        clash = repo.get_claude_plugin_by_key(conn, merged["name"], merged["marketplace"])
        if clash is not None and clash["id"] != plugin_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"plugin '{merged['name']}@{merged['marketplace']}' exists",
            )
    return repo.update_claude_plugin(conn, plugin_id, **fields)


@router.delete("/plugins/{plugin_id}")
def delete_plugin(
    plugin_id: int,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    plugin = _plugin_or_404(conn, plugin_id, actor)
    _require_edit(actor, plugin, "plugin")
    repo.delete_claude_plugin(conn, plugin_id)
    return {"deleted": f"{plugin['name']}@{plugin['marketplace']}"}


# ---- model backends -------------------------------------------------------------------
# Anthropic-API-compatible endpoints (a local model behind LiteLLM / claude-code-router,
# an LLM gateway) the spawn dropdown offers next to the Claude subscription. The control
# layer turns the selected row into that one agent's ANTHROPIC_* env at launch; the API
# key is encrypted at rest (HANDLER_SECRET_KEY) and never returned.


def _model_or_404(conn: Connection, model_id: int, actor: Actor) -> dict:
    row = repo.get_claude_model(conn, model_id)
    if row is None or not actor.can_view(row.get("owner_user_id")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"model {model_id} not found")
    return row


def _model_out(row: dict) -> dict:
    return {**row, "has_api_key": bool(row.get("api_key_enc"))}


def _encrypt_key_or_400(value: str) -> str:
    try:
        return secretstore.encrypt(value)
    except secretstore.SecretStoreError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"cannot store the API key: {exc}"
        ) from exc


@router.get("/models", response_model=list[ClaudeModelOut])
def list_models(
    actor: Actor = Depends(get_actor), conn: Connection = Depends(db_conn)
) -> list[dict]:
    return [
        _model_out(m) for m in repo.list_claude_models(conn, visible_to=actor.visible_scope)
    ]


@router.post(
    "/models",
    response_model=ClaudeModelOut,
    status_code=status.HTTP_201_CREATED,
)
def create_model(
    body: ClaudeModelIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    _require_create(actor)
    if repo.get_claude_model_by_name(conn, body.name) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"model '{body.name}' exists")
    api_key_enc = _encrypt_key_or_400(body.api_key) if body.api_key else None
    return _model_out(
        repo.create_claude_model(
            conn,
            body.name,
            body.base_url,
            body.model,
            api_key_enc=api_key_enc,
            small_fast_model=body.small_fast_model,
            harness=body.harness,
            env=body.env,
            enabled=body.enabled,
            owner_user_id=actor.user_id,
        )
    )


@router.patch("/models/{model_id}", response_model=ClaudeModelOut)
def update_model(
    model_id: int,
    body: ClaudeModelUpdateIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    _require_edit(actor, _model_or_404(conn, model_id, actor), "model")
    fields = body.model_dump(exclude_unset=True)
    if "name" in fields:
        clash = repo.get_claude_model_by_name(conn, fields["name"])
        if clash is not None and clash["id"] != model_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"model '{fields['name']}' exists"
            )
    # api_key / clear_api_key are write-only verbs, translated to the encrypted column.
    api_key = fields.pop("api_key", None)
    clear = fields.pop("clear_api_key", False)
    if api_key:
        fields["api_key_enc"] = _encrypt_key_or_400(api_key)
    elif clear:
        fields["api_key_enc"] = None
    return _model_out(repo.update_claude_model(conn, model_id, **fields))


@router.delete("/models/{model_id}")
def delete_model(
    model_id: int,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    row = _model_or_404(conn, model_id, actor)
    _require_edit(actor, row, "model")
    repo.delete_claude_model(conn, model_id)
    return {"deleted": row["name"]}


# ---- permissions ----------------------------------------------------------------------


def _permissions_out(stored: dict | None) -> dict:
    s = get_settings()
    stored = stored or {}
    return {
        "default_mode": stored.get("default_mode"),
        "allow": stored.get("allow", []),
        "deny": stored.get("deny", []),
        "ask": stored.get("ask", []),
        "base_mode": s.headless_permission_mode,
        "base_allow": s.headless_allowed_tools_list,
    }


@router.get("/permissions", response_model=ClaudePermissionsOut)
def get_permissions(conn: Connection = Depends(db_conn)) -> dict:
    return _permissions_out(repo.get_claude_config(conn, "permissions"))


@router.put(
    "/permissions",
    response_model=ClaudePermissionsOut,
    dependencies=[Depends(require_admin)],
)
def put_permissions(body: ClaudePermissionsIn, conn: Connection = Depends(db_conn)) -> dict:
    stored = {
        "default_mode": body.default_mode,
        "allow": [r.strip() for r in body.allow if r.strip()],
        "deny": [r.strip() for r in body.deny if r.strip()],
        "ask": [r.strip() for r in body.ask if r.strip()],
    }
    repo.set_claude_config(conn, "permissions", stored)
    return _permissions_out(stored)
