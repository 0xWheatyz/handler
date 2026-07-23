"""Claude management: skills, MCP connectors, plugins, and permission overrides.

The dashboard's Claude page edits these rows directly — no worker round-trip, because
nothing here touches a live process. The control container reads the same tables at
every launch: skills sync to the worker's user-level ``~/.claude/skills``, connectors
become the run's ``--mcp-config`` file, and plugins/permissions fold into the generated
per-agent ``settings.json`` (``control.settings_gen`` / ``control.claude_gen``). Changes
therefore apply to the *next* launch of every agent, not to runs already in flight.

Reads take the normal token; writes take the admin token (they shape what every agent
is allowed to do). The login flow stays under ``/login`` — it needs the worker's tmux.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection

from ...config import get_settings
from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import (
    ClaudeConnectorIn,
    ClaudeConnectorOut,
    ClaudeConnectorUpdateIn,
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


# ---- skills ---------------------------------------------------------------------------


def _skill_or_404(conn: Connection, skill_id: int) -> dict:
    skill = repo.get_claude_skill(conn, skill_id)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"skill {skill_id} not found")
    return skill


def _skill_out(conn: Connection, row: dict) -> dict:
    """A skill row shaped for responses: auxiliary file *paths* attached (content stays
    server-side — it syncs to workers, the UI only lists what ships)."""
    files = repo.list_claude_skill_files(conn, row["id"])
    return {**row, "files": [f["path"] for f in files]}


@router.get("/skills", response_model=list[ClaudeSkillOut])
def list_skills(conn: Connection = Depends(db_conn)) -> list[dict]:
    return [_skill_out(conn, s) for s in repo.list_claude_skills(conn)]


@router.post(
    "/skills",
    response_model=ClaudeSkillOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_skill(body: ClaudeSkillIn, conn: Connection = Depends(db_conn)) -> dict:
    if repo.get_claude_skill_by_name(conn, body.name) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"skill '{body.name}' exists")
    return repo.create_claude_skill(
        conn, body.name, body.content, description=body.description, enabled=body.enabled
    )


@router.post(
    "/skills/install",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_skill_install(body: SkillInstallIn, conn: Connection = Depends(db_conn)) -> dict:
    """Run a pasted marketplace install prompt on the worker (which has ``claude`` and
    network) and import what it fetches as managed skills. The UI polls the returned
    command like any other control action; its result carries the imported skill names
    and claude's report of the defaults it chose."""
    return repo.enqueue_command(
        conn, "skill_install", payload={"prompt": body.prompt}, requested_by="operator:web"
    )


@router.patch(
    "/skills/{skill_id}", response_model=ClaudeSkillOut, dependencies=[Depends(require_admin)]
)
def update_skill(
    skill_id: int, body: ClaudeSkillUpdateIn, conn: Connection = Depends(db_conn)
) -> dict:
    _skill_or_404(conn, skill_id)
    fields = body.model_dump(exclude_unset=True)
    if "name" in fields:
        clash = repo.get_claude_skill_by_name(conn, fields["name"])
        if clash is not None and clash["id"] != skill_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"skill '{fields['name']}' exists"
            )
    return _skill_out(conn, repo.update_claude_skill(conn, skill_id, **fields))


@router.delete("/skills/{skill_id}", dependencies=[Depends(require_admin)])
def delete_skill(skill_id: int, conn: Connection = Depends(db_conn)) -> dict:
    skill = _skill_or_404(conn, skill_id)
    repo.delete_claude_skill(conn, skill_id)
    return {"deleted": skill["name"]}


# ---- connectors (MCP servers) ---------------------------------------------------------


def _connector_or_404(conn: Connection, connector_id: int) -> dict:
    connector = repo.get_claude_connector(conn, connector_id)
    if connector is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"connector {connector_id} not found"
        )
    return connector


@router.get("/connectors", response_model=list[ClaudeConnectorOut])
def list_connectors(conn: Connection = Depends(db_conn)) -> list[dict]:
    return repo.list_claude_connectors(conn)


@router.post(
    "/connectors",
    response_model=ClaudeConnectorOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_connector(body: ClaudeConnectorIn, conn: Connection = Depends(db_conn)) -> dict:
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
    )


@router.patch(
    "/connectors/{connector_id}",
    response_model=ClaudeConnectorOut,
    dependencies=[Depends(require_admin)],
)
def update_connector(
    connector_id: int, body: ClaudeConnectorUpdateIn, conn: Connection = Depends(db_conn)
) -> dict:
    current = _connector_or_404(conn, connector_id)
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


@router.delete("/connectors/{connector_id}", dependencies=[Depends(require_admin)])
def delete_connector(connector_id: int, conn: Connection = Depends(db_conn)) -> dict:
    connector = _connector_or_404(conn, connector_id)
    repo.delete_claude_connector(conn, connector_id)
    return {"deleted": connector["name"]}


# ---- plugins --------------------------------------------------------------------------


def _plugin_or_404(conn: Connection, plugin_id: int) -> dict:
    plugin = repo.get_claude_plugin(conn, plugin_id)
    if plugin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"plugin {plugin_id} not found")
    return plugin


@router.get("/plugins", response_model=list[ClaudePluginOut])
def list_plugins(conn: Connection = Depends(db_conn)) -> list[dict]:
    return repo.list_claude_plugins(conn)


@router.post(
    "/plugins",
    response_model=ClaudePluginOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_plugin(body: ClaudePluginIn, conn: Connection = Depends(db_conn)) -> dict:
    if repo.get_claude_plugin_by_key(conn, body.name, body.marketplace) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"plugin '{body.name}@{body.marketplace}' exists",
        )
    return repo.create_claude_plugin(
        conn, body.name, body.marketplace, body.marketplace_repo, enabled=body.enabled
    )


@router.patch(
    "/plugins/{plugin_id}", response_model=ClaudePluginOut, dependencies=[Depends(require_admin)]
)
def update_plugin(
    plugin_id: int, body: ClaudePluginUpdateIn, conn: Connection = Depends(db_conn)
) -> dict:
    current = _plugin_or_404(conn, plugin_id)
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


@router.delete("/plugins/{plugin_id}", dependencies=[Depends(require_admin)])
def delete_plugin(plugin_id: int, conn: Connection = Depends(db_conn)) -> dict:
    plugin = _plugin_or_404(conn, plugin_id)
    repo.delete_claude_plugin(conn, plugin_id)
    return {"deleted": f"{plugin['name']}@{plugin['marketplace']}"}


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
