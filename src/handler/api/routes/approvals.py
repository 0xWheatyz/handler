"""Branch approvals — read the standing verdicts, enqueue new ones.

Recording a verdict resolves the reviewed HEAD sha (which requires the working tree in the
control container), so ``POST`` enqueues an ``approve``/``reject`` command for the worker.
Operator verdicts set ``actor='operator:web'`` and no acting agent, which the deploy gate
treats as a genuine second party (satisfying the "no self-approval" rule).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Connection

from ...db import repository as repo
from ..deps import db_conn, require_admin, require_auth
from ..schemas import ApprovalIn, ApprovalOut, CommandOut

router = APIRouter(
    prefix="/projects/{project}/approvals",
    tags=["approvals"],
    dependencies=[Depends(require_auth)],
)


def _require_project(conn: Connection, project: str) -> None:
    if repo.get_project(conn, project) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"project '{project}' not found")


@router.get("", response_model=list[ApprovalOut])
def list_approvals(
    project: str,
    branch: str | None = Query(None),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    _require_project(conn, project)
    return repo.list_approvals(conn, project, branch=branch)


@router.post(
    "",
    response_model=CommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def enqueue_approval(
    project: str, body: ApprovalIn, conn: Connection = Depends(db_conn)
) -> dict:
    _require_project(conn, project)
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
        requested_by="operator:web",
    )
