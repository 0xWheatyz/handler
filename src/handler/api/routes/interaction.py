"""Answer + resume — the async replacement for a human sitting at the tmux TTY.

``answer`` writes the operator's reply into the log entry that recorded the question
(the sole API mutation of ``log_entries``). ``resume`` then feeds that answer back to
the agent via ``claude --resume``, routed through the control-layer seam so it stays
mockable and the API/control boundary is explicit. They are two endpoints (README 3.3)
so the operator can answer many questions, then resume.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Connection

from ...control import spawn
from ...db import repository as repo
from ..deps import db_conn, require_auth
from ..schemas import AnswerIn, AnswerOut, ResumeIn, ResumeOut
from .common import resolve_agent

router = APIRouter(
    prefix="/projects/{project}/agents/{name}",
    tags=["interaction"],
    dependencies=[Depends(require_auth)],
)


@router.post("/answer", response_model=AnswerOut)
def answer(
    project: str,
    name: str,
    body: AnswerIn,
    conn: Connection = Depends(db_conn),
) -> AnswerOut:
    agent = resolve_agent(conn, project, name)

    if body.log_entry_id is not None:
        log_entry_id = body.log_entry_id
    else:
        open_q = repo.get_latest_open_question(conn, agent["id"])
        if open_q is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="no open question to answer; pass log_entry_id explicitly",
            )
        log_entry_id = open_q["id"]

    updated = repo.update_log_answer(conn, log_entry_id, body.answer)
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="log entry not found")

    # The question is answered but the agent is not resumed yet; leave status as
    # paused_for_input until /resume actually feeds it back.
    return AnswerOut(log_entry_id=log_entry_id, answered=True)


@router.post("/resume", response_model=ResumeOut)
def resume(
    project: str,
    name: str,
    body: ResumeIn,
    conn: Connection = Depends(db_conn),
) -> ResumeOut:
    agent = resolve_agent(conn, project, name)

    answer_text = body.answer
    if answer_text is None:
        open_q = repo.get_latest_open_question(conn, agent["id"])
        # The just-answered question no longer counts as open, so pull the most recent
        # answered entry if no explicit answer was supplied.
        if open_q is not None and open_q.get("answer"):
            answer_text = open_q["answer"]
        else:
            recent = repo.get_log(conn, agent["id"], limit=1)
            if recent and recent[0].get("answer"):
                answer_text = recent[0]["answer"]
    if not answer_text:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="no answer available to resume with; answer first or pass one",
        )

    ok, detail = spawn.resume(agent, answer_text)
    if ok:
        repo.set_agent_status(conn, agent["id"], "working")
    return ResumeOut(agent=name, resumed=ok, detail=detail)
