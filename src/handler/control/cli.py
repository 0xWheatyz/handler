"""``handler`` CLI — the control layer's write side.

Spawn/list/attach/kill manage agent processes. Phase 2 adds the forge-workflow control
commands: ``approve``/``reject`` (the senior agent records its verdict, which the deploy
gate checks), ``poll-ci`` (backfill CI verdicts), and ``forge-init`` (write the role
skills into a managed repo). The DB is the source of truth for what agents exist; tmux is
cross-checked for liveness. All commands are project-namespaced.
"""

from __future__ import annotations

import argparse
import os
import sys

from ..db import repository as repo
from ..db.engine import connection
from . import poller, skills_gen, spawn, tmux, worker


def _cmd_spawn(args: argparse.Namespace) -> int:
    try:
        agent = spawn.spawn(
            args.project,
            args.name,
            subdir=args.dir,
            worktree_branch=args.worktree,
            task=args.task,
            role=args.role,
        )
    except spawn.SpawnError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"spawned agent '{agent['name']}' (id={agent['id']}) in project '{args.project}'")
    print(f"  working_dir: {agent['working_dir']}")
    if args.role:
        print(f"  role: {args.role}")
    if agent.get("forge_note"):
        print(f"  warning: {agent['forge_note']}", file=sys.stderr)
    print(f"  tmux session: {tmux.session_name(args.project, args.name)}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    live = set(tmux.list_sessions())
    with connection() as conn:
        if args.project:
            projects = [args.project] if repo.get_project(conn, args.project) else []
        else:
            projects = [p["id"] for p in repo.list_projects(conn)]
        for project_id in projects:
            for agent in repo.list_agents(conn, project_id):
                session = tmux.session_name(project_id, agent["name"])
                alive = "live" if session in live else "-"
                role = agent.get("role") or "-"
                print(
                    f"{project_id}/{agent['name']}\t{role}\t{agent['status']}\t{alive}\t{session}"
                )
    return 0


def _cmd_attach(args: argparse.Namespace) -> int:
    session = tmux.session_name(args.project, args.name)
    if not tmux.has_session(session):
        print(f"error: no live session '{session}'", file=sys.stderr)
        return 1
    # Replace this process with an interactive tmux attach.
    os.execvp("tmux", ["tmux", "attach", "-t", session])
    return 0  # pragma: no cover - execvp does not return


def _cmd_kill(args: argparse.Namespace) -> int:
    try:
        spawn.kill(args.project, args.name)
    except spawn.SpawnError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"killed '{args.project}/{args.name}'")
    return 0


def _resolve_identity(args: argparse.Namespace) -> tuple[str, int] | None:
    """Resolve (project_id, acting_agent_id) for approve/reject from flags or env.

    The senior agent runs these from inside its session, where ``HANDLER_PROJECT_ID`` /
    ``HANDLER_AGENT_ID`` are set; flags override for manual/operator use. The acting
    agent must exist — the approval FK and the gate's "different agent" check both rely
    on a real agent id.
    """
    project_id = args.project or os.environ.get("HANDLER_PROJECT_ID")
    agent_id_raw = args.by_agent or os.environ.get("HANDLER_AGENT_ID")
    if not project_id:
        print("error: no project (pass --project or set HANDLER_PROJECT_ID)", file=sys.stderr)
        return None
    if not agent_id_raw:
        print(
            "error: no acting agent (pass --by-agent or set HANDLER_AGENT_ID)",
            file=sys.stderr,
        )
        return None
    with connection() as conn:
        agent = repo.get_agent_by_id(conn, int(agent_id_raw))
        if agent is None or agent["project_id"] != project_id:
            print(
                f"error: agent id={agent_id_raw} not found in project '{project_id}'",
                file=sys.stderr,
            )
            return None
    return project_id, int(agent_id_raw)


def _record_verdict(args: argparse.Namespace, status: str) -> int:
    resolved = _resolve_identity(args)
    if resolved is None:
        return 1
    project_id, agent_id = resolved

    # Pin an approval to the reviewed commit so later pushes to the branch invalidate it.
    # Prefer an explicit --sha; otherwise read HEAD of the reviewing agent's working dir.
    approved_sha = args.sha
    if approved_sha is None and status == "approved":
        from . import gitops

        with connection() as conn:
            agent = repo.get_agent_by_id(conn, agent_id)
        if agent is not None:
            approved_sha = gitops.head_sha(agent["working_dir"])

    with connection() as conn:
        approval = repo.record_approval(
            conn,
            project_id=project_id,
            branch=args.branch,
            status=status,
            approved_by_agent_id=agent_id,
            pr_ref=args.pr,
            note=args.note,
            approved_sha=approved_sha,
        )
    sha_note = f" @ {approved_sha[:12]}" if approved_sha else ""
    print(
        f"{status} branch '{args.branch}'{sha_note} in '{project_id}' "
        f"(approval id={approval['id']}, by agent id={agent_id})"
    )
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    return _record_verdict(args, "approved")


def _cmd_reject(args: argparse.Namespace) -> int:
    return _record_verdict(args, "rejected")


def _cmd_poll_ci(args: argparse.Namespace) -> int:
    if args.watch:
        for summary in poller.watch(project_id=args.project, interval=args.interval):
            print(
                f"sweep: checked={summary['checked']} resolved={summary['resolved']} "
                f"pending={summary['pending']}"
            )
        return 0  # pragma: no cover - watch loops until interrupted
    summary = poller.sweep(project_id=args.project)
    print(
        f"checked={summary['checked']} resolved={summary['resolved']} "
        f"pending={summary['pending']}"
    )
    return 0


def _cmd_forge_init(args: argparse.Namespace) -> int:
    with connection() as conn:
        project = repo.get_project(conn, args.project)
    if project is None:
        print(f"error: project '{args.project}' not registered", file=sys.stderr)
        return 1
    root = project["root_dir"]
    written = skills_gen.write_skills(root)
    print(f"wrote {len(written)} forge skill file(s) under {root}/.claude/skills/")
    if not args.no_commit:
        from . import gitops

        rel = os.path.join(".claude", "skills")
        ok_add, _ = gitops.add(root, [rel])
        ok_commit, out = gitops.commit(root, "chore: add handler forge-workflow skills")
        if ok_add and ok_commit:
            print("committed the skills into the repo")
        else:
            print(f"note: could not auto-commit ({out}); commit {rel} yourself", file=sys.stderr)
    return 0


def _cmd_worker(args: argparse.Namespace) -> int:
    print(
        f"worker starting (poll={args.interval}s, ci-sweep={args.ci_interval}s); "
        "draining control commands + sweeping CI"
    )
    worker.run(poll_interval=args.interval, ci_interval=args.ci_interval)
    return 0  # pragma: no cover - run loops until interrupted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="handler", description="Handler control layer")
    sub = parser.add_subparsers(dest="command", required=True)

    p_spawn = sub.add_parser("spawn", help="spawn an agent")
    p_spawn.add_argument("--project", required=True)
    p_spawn.add_argument("--name", required=True)
    p_spawn.add_argument("--role", choices=["junior", "senior", "deploy"], help="workflow role")
    group = p_spawn.add_mutually_exclusive_group()
    group.add_argument("--worktree", metavar="BRANCH", help="git worktree on BRANCH")
    group.add_argument("--dir", metavar="SUBDIR", help="subdirectory under project root")
    p_spawn.add_argument("--task", help="initial task/prompt for the agent")
    p_spawn.set_defaults(func=_cmd_spawn)

    p_list = sub.add_parser("list", help="list agents")
    p_list.add_argument("--project", help="limit to one project")
    p_list.set_defaults(func=_cmd_list)

    p_attach = sub.add_parser("attach", help="attach to an agent's tmux session")
    p_attach.add_argument("--project", required=True)
    p_attach.add_argument("--name", required=True)
    p_attach.set_defaults(func=_cmd_attach)

    p_kill = sub.add_parser("kill", help="kill an agent's session")
    p_kill.add_argument("--project", required=True)
    p_kill.add_argument("--name", required=True)
    p_kill.set_defaults(func=_cmd_kill)

    for verb, helptext, fn in (
        ("approve", "approve a branch for merge/deploy", _cmd_approve),
        ("reject", "reject a branch (request changes)", _cmd_reject),
    ):
        p = sub.add_parser(verb, help=helptext)
        p.add_argument("--branch", required=True, help="the branch being reviewed")
        p.add_argument("--project", help="defaults to $HANDLER_PROJECT_ID")
        p.add_argument(
            "--by-agent", type=int, help="acting agent id; defaults to $HANDLER_AGENT_ID"
        )
        p.add_argument("--pr", help="optional forge PR number/URL")
        p.add_argument("--note", help="reason / review notes")
        p.add_argument("--sha", help="pin the approval to this commit (defaults to HEAD)")
        p.set_defaults(func=fn)

    p_poll = sub.add_parser("poll-ci", help="backfill CI verdicts for pending pushes")
    p_poll.add_argument("--project", help="limit to one project")
    p_poll.add_argument("--watch", action="store_true", help="loop instead of a single sweep")
    p_poll.add_argument("--interval", type=float, default=30.0, help="seconds between sweeps")
    p_poll.set_defaults(func=_cmd_poll_ci)

    p_forge = sub.add_parser("forge-init", help="write the forge-workflow skills into a repo")
    p_forge.add_argument("--project", required=True)
    p_forge.add_argument("--no-commit", action="store_true", help="write but don't git-commit")
    p_forge.set_defaults(func=_cmd_forge_init)

    p_worker = sub.add_parser(
        "worker", help="run the control worker: drain enqueued commands + sweep CI"
    )
    p_worker.add_argument(
        "--interval", type=float, default=2.0, help="seconds to idle when the queue is empty"
    )
    p_worker.add_argument(
        "--ci-interval", type=float, default=30.0, help="seconds between CI sweeps (0 disables)"
    )
    p_worker.set_defaults(func=_cmd_worker)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
