"""Generate the role-based forge-workflow skills committed into a managed repo.

Phase 2 surfaces forge to the *agents* as Claude Code skills, not to the operator as
CLI/API commands. The operator only configures credentials + the version pin; the agents
then drive the whole dev workflow — junior writes and opens a PR, senior reviews and
records an approval, deploy merges and ships once approved — using ``forge`` (already
authenticated by the injected credentials) and the ``handler`` approval commands.

These skills are *committed into the managed repo* (``.claude/skills/<name>/SKILL.md``)
so they travel with the code and are visible to humans, not regenerated per agent. Each
role's agent naturally follows the skill matching its role; the hard approval gate in
``hooks.gate`` enforces the handoff regardless of what any skill says.
"""

from __future__ import annotations

import os

# One skill per role, plus a short workflow overview. Kept as plain data so the writer is
# trivial and the content is easy to review/diff. Each entry is (dirname, front-matter
# name, description, body).
_SKILLS: list[tuple[str, str, str, str]] = [
    (
        "forge-workflow",
        "forge-workflow",
        "Overview of the junior -> senior -> deploy forge workflow this repo uses.",
        """# Forge workflow (junior -> senior -> deploy)

This repository is worked by three cooperating Handler agents, each a separate context:

1. **junior** — writes the change on a feature branch and opens a pull request.
2. **senior** — reviews that pull request and records an approval (or requests changes).
3. **deploy** — merges the approved branch and deploys it.

`forge` is already authenticated in this environment (Handler injected the project's
credentials), so it works the same whether the host is GitHub, GitLab, Gitea/Forgejo, or
Bitbucket. Handler enforces the handoffs with hard gates you cannot talk your way past:

- A `git push` is blocked unless the tests **and** a throwaway image build pass locally.
- A **merge or deploy** — and a direct push to a protected branch (`main`/`master`) — is
  blocked unless a *standing approval* exists for the current branch, made by a
  **different** agent than the one merging. There is no self-approval, and the approval is
  pinned to the reviewed commit: pushing new commits invalidates it and forces re-review.

Follow the skill for your role: `forge-junior`, `forge-senior`, or `forge-deploy`.
""",
    ),
    (
        "forge-junior",
        "forge-junior",
        "Junior dev role: implement the change on a feature branch and open a PR.",
        """# Role: junior developer

You write the change. You do **not** merge or deploy it.

1. Create a feature branch for the work:
   ```bash
   forge branch create feat/<short-name>   # or: git checkout -b feat/<short-name>
   ```
2. Implement the change. Commit in small, coherent steps.
3. Before pushing, make sure the tests pass — the push gate will block you otherwise:
   ```bash
   mise run test
   ```
4. Push and open a pull request for review:
   ```bash
   git push -u origin feat/<short-name>
   forge pr create --title "<what changed>" --body "<why, and how to verify>"
   ```
5. Your checkmark should now read *needs review*. Stop here. A **senior** agent picks it
   up next — do not merge your own work; the approval gate will refuse it anyway.
""",
    ),
    (
        "forge-senior",
        "forge-senior",
        "Senior dev role: review the open PR and record an approval or request changes.",
        """# Role: senior reviewer

You review a junior's pull request and record a verdict. You do **not** write the feature
or deploy it.

1. Find the branch/PR under review and check it out so you can read the real diff:
   ```bash
   forge pr list
   forge pr checkout <pr-number>       # or: git fetch && git checkout feat/<name>
   ```
2. Review thoroughly: correctness, tests, security, and that `mise run test` passes.
3. Record your verdict — this is what the deploy gate checks. Handler reads your identity
   and project from the environment; name the branch you reviewed:
   ```bash
   # approve:
   handler approve --branch feat/<name> --pr <pr-number> --note "<why it's good>"
   # or request changes:
   handler reject  --branch feat/<name> --note "<what must change>"
   ```
4. On approval, hand off to the **deploy** agent. On rejection, hand back to the junior.

Your approval only counts because you are a *different* agent than the author — that
separation is the whole point of the gate. It is also pinned to the exact commit you
reviewed: if the junior pushes more commits afterwards, your approval no longer applies
and you must review again.
""",
    ),
    (
        "forge-deploy",
        "forge-deploy",
        "Deploy engineer role: merge the approved branch and deploy it.",
        """# Role: deployment engineer

You merge and ship an already-approved branch. You do **not** review or approve it.

1. Check out the branch that was approved so you are *on* it (the gate checks the current
   branch's approval):
   ```bash
   git fetch && git checkout feat/<name>
   ```
2. Merge and deploy. Both are gated — if there is no standing approval for this branch
   from a different agent, Handler denies the command and tells you why:
   ```bash
   forge pr merge <pr-number>     # blocked without an approval
   mise run deploy                # blocked without an approval
   ```
3. After the push/merge lands, CI does the authoritative build-and-deploy on its own
   runner. Handler's poller records the CI verdict back onto the log entry for that
   commit; you don't need to watch it manually.
""",
    ),
]


def skill_files() -> dict[str, str]:
    """Return ``relative_path -> file_contents`` for every generated skill file."""
    files: dict[str, str] = {}
    for dirname, name, description, body in _SKILLS:
        front = f"---\nname: {name}\ndescription: {description}\n---\n\n"
        files[os.path.join(".claude", "skills", dirname, "SKILL.md")] = front + body
    return files


def write_skills(repo_root: str) -> list[str]:
    """Write the role skills under ``repo_root/.claude/skills/``; return written paths."""
    written: list[str] = []
    for rel_path, contents in skill_files().items():
        abs_path = os.path.join(repo_root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w") as fh:
            fh.write(contents)
        written.append(abs_path)
    return written
