"""``handler`` CLI — spawn/list/attach/kill.

The DB is the source of truth for what agents exist; tmux is cross-checked for
liveness. All commands are project-namespaced.
"""

from __future__ import annotations

import argparse
import os
import sys

from ..db import repository as repo
from ..db.engine import connection
from . import spawn, tmux


def _cmd_spawn(args: argparse.Namespace) -> int:
    try:
        agent = spawn.spawn(
            args.project,
            args.name,
            subdir=args.dir,
            worktree_branch=args.worktree,
            task=args.task,
        )
    except spawn.SpawnError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"spawned agent '{agent['name']}' (id={agent['id']}) in project '{args.project}'")
    print(f"  working_dir: {agent['working_dir']}")
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
                print(f"{project_id}/{agent['name']}\t{agent['status']}\t{alive}\t{session}")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="handler", description="Handler control layer")
    sub = parser.add_subparsers(dest="command", required=True)

    p_spawn = sub.add_parser("spawn", help="spawn an agent")
    p_spawn.add_argument("--project", required=True)
    p_spawn.add_argument("--name", required=True)
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
