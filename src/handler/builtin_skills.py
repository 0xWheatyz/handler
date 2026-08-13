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
