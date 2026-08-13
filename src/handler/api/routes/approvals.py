"""Branch approvals — read the standing verdicts, enqueue new ones.

Recording a verdict resolves the reviewed HEAD sha (which requires the working tree in the
control container), so ``POST`` enqueues an ``approve``/``reject`` command for the worker.
Operator verdicts set ``actor='operator:web'`` and no acting agent, which the deploy gate
treats as a genuine second party (satisfying the "no self-approval" rule).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import Actor, db_conn, get_actor, require_auth
from ..schemas import ApprovalIn, ApprovalOut, CommandOut
from .common import resolve_project

router = APIRouter(
    prefix="/projects/{project}/approvals",
    tags=["approvals"],
    dependencies=[Depends(require_auth)],
)


@router.get("", response_model=list[ApprovalOut])
def list_approvals(
    project: str,
    branch: str | None = Query(None),
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    resolve_project(conn, project, actor)
    return repo.list_approvals(conn, project, branch=branch)


@router.post(
    "",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_approval(
    project: str,
    body: ApprovalIn,
    actor: Actor = Depends(get_actor),
    conn: Connection = Depends(db_conn),
) -> dict:
    resolve_project(conn, project, actor, edit=True)
    payload = {
        "branch": body.branch,
        "sha": body.sha,
        "pr": body.pr,
        "note": body.note,
    }
    # Verdict ('approved'/'rejected') -> command type ('approve'/'reject').
    command_type = "approve" if body.status == "approved" else "reject"
    return repo.enqueue_command(
        conn,
        command_type,
        project_id=project,
        agent_name=body.agent_name,
        payload={k: v for k, v in payload.items() if v is not None},
        requested_by=actor.label,
    )
