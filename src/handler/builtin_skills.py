"""Built-in operator skills, seeded into the managed skill store on API startup.

These cover the judgment layer the hard gates cannot enforce: the gates check that
tests *pass* before a turn ends or a push leaves, but not that an agent responded to a
blocked gate sensibly, tested new behavior, left a useful checkpoint, kept the shared
memory clean, shaped ``mise`` tasks honestly, carried state across scheduled runs, or
kept injected credentials out of logs. Shipping them with Handler means every install
starts with the same baseline instead of each operator rediscovering the list.

Seeding is idempotent **by name**: a row that already exists is never touched, so an
operator's edits and enable/disable choices survive every upgrade. Deleting a built-in
brings it back (as shipped) on the next API start — disabling is the supported
off-switch. The rows are ordinary shared skills after seeding: visible to everyone,
admin-editable, synced to workers like any other managed skill.
"""

from __future__ import annotations

from sqlalchemy import Connection

from .db import repository as repo

# One entry per skill: (name, description, body). The body is the SKILL.md markdown
# minus front-matter (claude_gen adds name/description at sync time). Kept as plain
# data so the content is easy to review and diff, exactly like skills_gen._SKILLS.
BUILTIN_SKILLS: list[tuple[str, str, str]] = [
    (
        "handler-quiet-output",
        "Work through tool calls, not prose: the transcript is not the deliverable. "
        "Keep a minimized NOTES.md ledger instead. Always applies.",
        """# Quiet output: tools and notes, not prose

Nobody watches your transcript live, and nobody reads it afterwards — the operator
reads NOTES.md, the checkmark, and memory. Narration is spent tokens that bury the
information somewhere no one will look for it.

## Work through tool calls

- Don't announce what you're about to do, recap what you just did, or restate file
  contents — the tool calls are the record.
- No essays or running commentary in the transcript. A plan worth keeping goes in
  NOTES.md; a plan not worth keeping isn't worth typing.
- The one message that matters is your **final** one: the Stop hook captures it onto
  the checkmark. Keep it checkpoint-sized — a few lines of status, not a report.

## NOTES.md is the output

Maintain `NOTES.md` at the repo root (create it if missing) as a minimized running
ledger, committed with your work:

- One bullet per meaningful action: what changed, where, and why in one line —
  `- fixed retry loop in poller.py (cause: timeout treated as success)`.
- Facts, not narration. Bullets, not paragraphs. No restated diffs — the commits
  hold the code.
- Append under a dated/session heading; don't rewrite earlier sessions' entries.
- Scheduled runs: your prompt's state file serves this role — keep one file, not two.

## Route everything to its store

- **What happened, how**: NOTES.md.
- **Problems, surprises, causes**: memory (gotcha/decision notes) — durable and
  shared, per the memory skill.
- **Current status + next step**: the final checkpoint message.
- **Questions**: the question tool (AskUserQuestion; `ask_operator` on the pi
  harness), never prose. A deferred question reaches the operator as a push
  notification and an answer prompt in the web and mobile apps; a question typed
  into the transcript reaches no one and stalls the run.
""",
    ),
    (
        "handler-gate-recovery",
        "What to do when the completion gate or push gate blocks you. Use whenever "
        "a Stop hook or git push is denied with a test/build failure.",
        """# Recovering from a blocked gate

Handler denies `git push` until `mise run test` and the image build pass, and blocks
ending your turn while tests fail or work is uncommitted/unpushed. A blocked gate is
information, not an obstacle.

## Do

1. **Read the gate's output.** The denial reason contains the failing output. Diagnose
   from it; don't re-run blindly.
2. **Fix the real failure**, re-run `mise run test` yourself, then retry the push or
   finish the turn.
3. If the failure is pre-existing (reproduces on a clean checkout of the base branch),
   say so in your checkpoint and raise it as an open question instead of burying it.

## Never

- Delete, skip, `xfail`, or weaken a test to get green. The gate checks that tests
  pass — making them meaningless defeats the entire system.
- Edit the `test` task in mise config to dodge the gate (changing what "test" means is
  an operator decision).
- Use `git push --no-verify`, force-push over shared history, or amend away work to
  look clean.
- Loop more than 3 times on the same failure without changing your diagnosis. Ask the
  operator instead — a deferred question costs minutes; a wrong "fix" costs a review.
""",
    ),
    (
        "handler-testing",
        "Test authorship standard: every behavior change lands with a test that fails "
        "without it. Use whenever writing or changing code.",
        """# Testing standard

The gates verify that tests pass — only you can make the tests worth passing.

- **Every behavior change ships with a test that fails without the change.** Write it,
  watch it fail (or reason precisely about why it would), then make it pass. A diff
  with no test change needs a stated reason in the commit message.
- Test the edge you were worried about, not just the happy path: empty inputs, the
  boundary value, the error branch, the concurrent/second call.
- Bug fixes start from a reproducing test; the fix is done when that test passes.
- Keep the suite fast and deterministic: no real network, no sleeps for timing, no
  order dependence. The verification gate kills runs at 30 minutes — a slow suite
  taxes every agent and every push on this project after you.
- Match the project's existing test layout and naming; put the test where the next
  reader would look for it.
""",
    ),
    (
        "handler-checkpoints",
        "How to leave checkpoints and ask operator questions that read well on a "
        "phone. Use when checkpointing, finishing, or getting blocked.",
        """# Checkpoints the operator can act on

Your checkmark is one small row the operator reads on a dashboard or phone. Write it
for a glance, not a scroll.

- **Where it stopped**: one concrete sentence about state, not activity. "Auth
  refactor done, 2 endpoints left (list/export)" beats "working on refactoring".
- **Next steps**: the 1-3 actions the *next* session should take, specific enough to
  start from cold. Assume the next session has no memory of this one.
- **Open question**: ask only decisions the operator alone can make (scope, tradeoffs,
  credentials, destructive actions) — never things you can determine from the code.
  Make it answerable in one line, state your recommended default, and keep working on
  what isn't blocked by the answer.
- When a question is answered, act on the answer; don't re-ask variants of it.
- Blocked entirely? Say exactly what unblocks you. "Blocked: need FOO_API_KEY set on
  the worker" is actionable; "having trouble" is not.
""",
    ),
    (
        "handler-memory",
        "When to search and what to save in the shared agent memory. Use at task "
        "start and before finishing any nontrivial task.",
        """# Using the shared memory well

Handler injects relevant notes at session start and gives you memory tools. The store
is shared across all agents and all future runs — its quality compounds either way.

## Before starting

Search memory for the components you're about to touch. A past agent may have already
hit your problem; re-deriving a solved gotcha wastes your whole session's advantage.

## Worth saving

- **gotcha** — a surprising failure + its cause + the fix ("X hangs unless Y").
- **decision** — a choice with alternatives and the reason ("chose A over B because…").
- **runbook** — steps that took real effort to discover and will be needed again.
- **fact** — a stable, non-obvious property of the system.

## Not worth saving

Narration ("implemented the endpoint"), anything in the repo's own docs, task status
(that's the checkpoint's job), or secrets/credentials — never store those.

Write notes for a reader with zero context from your session: name the project and
component, keep the title a one-line takeaway, link related notes when you know them.
""",
    ),
    (
        "handler-mise-tasks",
        "Rules for the mise task contract: test must stay honest, deterministic, and "
        "fast. Use when creating or editing mise.toml / .mise.toml.",
        """# The mise task contract

`mise run test` is Handler's entire verification contract: the completion gate and the
push gate both call it. Whatever it runs is what "verified" means for this repo.

- `[tasks.test]` runs the real suite — unit + fast integration — deterministically:
  exit 0 only when the code is actually healthy, no reliance on external services,
  no flaky timing. Aim for minutes; the gate kills runs at 30.
- **Never narrow `test` to make a gate pass.** Removing a slow-but-real check to get
  green is an operator decision; propose it as an open question with the numbers.
- `[tasks.build-image]` (when the repo deploys as an image) does a throwaway local
  build — no registry pushes, no deploy side effects. The push gate runs it after
  tests.
- Bootstrapping a new repo: prefer the stack's native runner (pytest, npm test, go
  test, cargo test) wired thinly through mise, not a custom script. Keep task
  definitions readable — the operator reviews them like code, because they are the
  gate.
""",
    ),
    (
        "handler-scheduled-runs",
        "Continuity pattern for scheduled (recurring) runs: read the state file, do "
        "one increment, overwrite it. Use when your task mentions a notes/state file "
        "or you are a scheduled run.",
        """# Scheduled-run continuity

Scheduled runs are stateless: every firing is a fresh agent with no memory of the
last one. Continuity lives in a state file in the repo (conventionally `notes.md`,
or whatever file your prompt names).

1. **Read the state file first.** It tells you where the last run stopped and what's
   next. Missing file = first run: create it and define the plan.
2. **Do one clean increment** of the recurring task — something that fits comfortably
   in a single session and merges safely. Don't start what the next run can't pick up.
3. **Overwrite the state file before finishing** with: current status, exactly where
   you stopped, the next step, and anything surprising you learned. Write it for a
   reader with zero context — that reader is the next run.
4. Commit the state file with your work; it must be pushed to exist for the next run.

If the state file says the recurring task is complete, verify that claim briefly and
then leave a checkpoint question asking the operator whether to disable the schedule
— don't invent new scope to fill the run.
""",
    ),
    (
        "handler-secrets",
        "Credential hygiene: Handler injects tokens and keys — keep them out of "
        "logs, commits, and PRs. Always applies.",
        """# Secrets hygiene

Handler injects credentials into your environment (forge tokens, model API keys,
whatever the operator configured). They are for tools to use, not for output.

- Never print credential values: no `env` dumps, no `echo $TOKEN`, no logging config
  objects that embed keys. If you must verify one exists, test for presence
  (`[ -n "$TOKEN" ]`), not value.
- Never commit secrets: no `.env` files, no tokens in code, config samples use
  placeholders (`YOUR_KEY_HERE`). If a repo needs new secret config, add the *name*
  to an example file and raise a checkpoint question for the operator to set the
  value.
- Never paste credentials into commit messages, PR titles/bodies, review comments, or
  memory notes — all of those outlive the session and leave the machine.
- Committed a secret anyway? Do not just delete it in a follow-up commit (history
  keeps it). Stop, leave an open question naming the credential so the operator can
  rotate it, and say exactly which commit is affected.
""",
    ),
    (
        "handler-dispatch",
        "How to hand work to a new agent with dispatch_agent: when a handoff is "
        "warranted, and how to write a task the receiving agent can act on cold. "
        "Use whenever you are considering dispatching.",
        """# Handing work to another agent

`dispatch_agent` queues a **new agent** in your project, starting as soon as a worker
is free. It exists so a pipeline advances on a *result* instead of on a timer: the
step that knows whether there is work is the step that starts the next one.

## Dispatch when — and only when — there is real work

- One dispatch per thing you actually found. A handoff, not a fan-out.
- **Finding nothing is a complete, successful run.** Say so in your final message and
  end your turn. Do not dispatch "just to check", do not dispatch a placeholder, and
  do not dispatch work you could finish yourself in this run.
- Don't dispatch to dodge a blocked gate. A failing test is yours to fix.

## Write the task for someone with no context

The new agent starts cold: it never saw your session, your search results, or your
reasoning. Its whole world is the `task` string you write. So:

- State the outcome, not the backstory: "Implement @specs/2026-08-19-foo.md" beats
  "continue what I was looking at".
- Name every file, path, URL, or identifier it needs. If a fact only exists in your
  transcript, it is lost — put it in the task, or save it to memory and say which note.
- Say what *done* looks like, and name any constraint you already know about.
- `reason` is for the operator reading Activity, not for the new agent: one line on
  why this handoff was warranted.

## Limits, and what they mean

Dispatch is capped per run and per chain depth; a refusal is not a bug to route
around. Hitting the per-run cap means you are fanning out — fold the rest into one
handoff. Hitting the depth cap means the chain has gone far enough without a human:
finish what you can and leave the rest in your checkpoint for the operator.

Your dispatch shows up in Activity as a normal queued spawn attributed to you, so the
operator can always see which agent started what.
""",
    ),
    (
        "handler-scout",
        "Role: scout — watch a source for genuinely new material, dedupe against a "
        "memory watermark, and hand findings to a planner. Use when your role is "
        "scout or your task is a recurring watch.",
        """# Role: scout

You watch a source and decide whether anything new is worth acting on. You do **not**
write code, write specs, or change the repo — a scout run should leave a clean tree.

Most of your runs will find nothing. That is the job working correctly, and it is what
makes the whole pipeline cheap: nothing downstream runs until you say there is work.

## Every run, in order

1. **Recall the watermark.** `memory_search` for your watch note (the one your task
   names, e.g. `watch:<topic>`). It lists the identifiers you have already handled —
   DOIs, arXiv ids, URLs, release tags, whatever your source uses. A `SessionStart`
   recall usually puts it in front of you before you ask.
2. **Query the source** your task names, over a window comfortably wider than your
   schedule's interval — overlap is free, a gap loses an item forever.
3. **Filter to genuinely new AND relevant.** Drop anything whose id is already in the
   watermark. Then drop anything that doesn't actually bear on the project's subject:
   a keyword match is not relevance, and passing junk downstream costs a full coding
   run. When you are unsure, prefer to skip and note why.
4. **Update the watermark** with `memory_save(note_id=...)` on the *same* note — every
   id you examined this run, whether or not you passed it on, so the next run doesn't
   re-examine it. Keep it a compact list, newest first; trim ids far older than could
   ever resurface.
5. **Report.**
   - *Nothing new:* end your turn with a one-line final message saying what you
     searched and that nothing qualified. No dispatch. Don't pad the run.
   - *Something new:* one `dispatch_agent` call with `role="planner"`, carrying the
     full citations (title, id/DOI, link, authors, date) and — in your own words — why
     it matters to this project and what it might change. Then end.

## Keep the run cheap

You are deliberately run on a small, cheap model on a short leash: read abstracts and
metadata first, and only fetch a full text when relevance genuinely turns on it. Don't
clone, don't build, don't run tests. Your entire output is a memory note and, on the
rare interesting day, one dispatch.
""",
    ),
    (
        "handler-planner",
        "Role: planner — turn source material into a committed spec, then dispatch "
        "an implementer. Use when your role is planner.",
        """# Role: planner

You turn raw material (a paper, a report, an operator brief) into a spec someone else
can implement without reading the source. You do **not** implement it yourself.

## The run

1. **Read the sources named in your task** — properly, not just the abstract. If a
   source is unreachable, say so in your checkpoint rather than guessing at it.
2. **Check what already exists.** `memory_search` for prior decisions on this topic,
   and look at the repo: the change may already be present, already rejected, or
   already specced. Saying "no change needed, here's why" is a valid outcome and a
   cheap one.
3. **Write `specs/<YYYY-MM-DD>-<slug>.md`** (create `specs/` if missing):
   - *Source* — citation and link, so the provenance survives you.
   - *Why* — what this changes about how the project should work.
   - *What to build* — concrete, in this codebase's terms: the files and functions to
     touch, the behavior to add, the interfaces involved.
   - *How to verify* — what test proves it, and what the expected result is.
   - *Out of scope* — what an implementer should explicitly not do here.
   Write for someone who never read the source. If the source doesn't support a
   concrete change, write that conclusion in the spec instead of inventing scope.
4. **Commit and push the spec** — it must exist in the repo before anyone can act on
   it, and the completion gate will hold you until it's pushed anyway.
5. **Dispatch the implementer:** one `dispatch_agent` with `role="junior"` and a task
   naming the spec path (`Implement @specs/<file>.md`) plus a one-line summary of the
   goal. From there the normal junior -> senior -> deploy workflow takes over.

If step 3 concluded no change is warranted, commit that spec anyway as the record —
and do **not** dispatch. A written "we looked and decided not to" is worth keeping.
""",
    ),
]


def seed_builtin_skills(conn: Connection) -> list[str]:
    """Insert any built-in skill whose name is not present; return the names created.

    Existing rows are never modified — operator edits, disables, and re-descriptions
    all survive. Rows are created enabled and unowned (shared), so they sync to every
    worker and are admin-editable like any managed skill.
    """
    created: list[str] = []
    for name, description, body in BUILTIN_SKILLS:
        if repo.get_claude_skill_by_name(conn, name) is not None:
            continue
        repo.create_claude_skill(conn, name, body, description=description, enabled=True)
        created.append(name)
    return created
