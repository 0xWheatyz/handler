/* Typed client for the Handler API + the row shapes it returns (mirrors the FastAPI
 * pydantic schemas in src/handler/api/schemas.py). The browser calls the API same-origin
 * with relative paths; set NEXT_PUBLIC_API_BASE to point `npm run dev` at another origin.
 *
 * NOTE: this file lives under frontend/lib/, now un-ignored in .gitignore so the source
 * ships and the build works from a fresh clone (the built export under
 * src/handler/api/static/ is what the package serves). */

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export type CommandStatus = "queued" | "running" | "done" | "failed";

export interface Project {
  id: string;
  root_dir: string;
  git_remote?: string | null;
  credential_ref?: string | null;
  created_at: string;
  /* Present on the registration response in git-server mode: the enqueued clone. */
  sync_command_id?: number | null;
  /* Present on the registration response when "Initialize mise" was ticked: the
   * enqueued bootstrap agent that writes + commits + pushes a .mise.toml. */
  mise_init_command_id?: number | null;
}

export interface Agent {
  id: number;
  project_id: string;
  name: string;
  working_dir: string;
  status: string;
  role?: string | null;
  /* Latest output snapshot from the worker: the tmux pane tail for legacy agents, the
   * latest assistant text for headless runs. For a crashed agent this is the evidence
   * frame — the last thing the process said. */
  last_output?: string | null;
  output_at?: string | null;
  /* Headless runner: claude session UUID (null = legacy tmux agent) + supervising worker. */
  session_id?: string | null;
  worker_id?: string | null;
  created_at: string;
}

/* One persisted stream-json event of a headless run (GET .../events, cursor-paged by id).
 * `type` mirrors the stream (system/assistant/user/result) plus `worker` (runner notices)
 * and `raw` (unparseable line kept verbatim). */
export interface AgentEvent {
  id: number;
  agent_id: number;
  run_id: number;
  session_id?: string | null;
  seq: number;
  type: string;
  payload?: Record<string, unknown> | null;
  created_at: string;
}

export interface Checkmark {
  agent_id: number;
  checkpoint_at: string;
  status: string;
  where_it_stopped?: string | null;
  next_steps?: string[] | null;
  open_question?: string | null;
  log_entry_id?: number | null;
  tests_status: string;
  tested_at?: string | null;
  build_status: string;
  built_at?: string | null;
}

export interface LogEntry {
  id: number;
  agent_id: number;
  created_at: string;
  session_id?: string | null;
  status: string;
  summary?: string | null;
  decisions?: string | null;
  question?: string | null;
  answer?: string | null;
  visibility: string;
  push_sha?: string | null;
  ci_status: string;
  ci_checked_at?: string | null;
}

export interface Approval {
  id: number;
  project_id: string;
  branch: string;
  approved_sha?: string | null;
  pr_ref?: string | null;
  status: string;
  approved_by_agent_id?: number | null;
  actor?: string | null;
  note?: string | null;
  created_at: string;
}

export interface Host {
  hostname: string;
  forge_type: string;
  token_env_var?: string | null;
  base_url?: string | null;
  ssh_public_key?: string | null;
  has_token: boolean;
  created_at: string;
}

export interface Command {
  id: number;
  project_id?: string | null;
  agent_name?: string | null;
  type: string;
  payload?: Record<string, unknown> | null;
  status: CommandStatus;
  result?: Record<string, unknown> | null;
  error?: string | null;
  requested_by?: string | null;
  claimed_by?: string | null;
  created_at: string;
  claimed_at?: string | null;
  finished_at?: string | null;
}

export interface Schedule {
  id: number;
  project_id: string;
  name_prefix: string;
  task: string;
  role?: string | null;
  worktree?: string | null;
  subdir?: string | null;
  interval_seconds: number;
  enabled: boolean;
  next_run_at: string;
  last_run_at?: string | null;
  last_command_id?: number | null;
  created_at: string;
}

/* ---- Claude management (the dashboard's Claude page) ---- */

export interface ClaudeSkill {
  id: number;
  name: string;
  description?: string | null;
  content: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export type McpTransport = "stdio" | "http" | "sse";

export interface ClaudeConnector {
  id: number;
  name: string;
  transport: McpTransport;
  command?: string | null;
  args?: string[] | null;
  env?: Record<string, string> | null;
  url?: string | null;
  headers?: Record<string, string> | null;
  enabled: boolean;
  created_at: string;
}

export interface ClaudePlugin {
  id: number;
  name: string;
  marketplace: string;
  marketplace_repo: string;
  enabled: boolean;
  created_at: string;
}

/* Stored overrides + the env baseline they merge over at launch (read-only here). */
export interface ClaudePermissions {
  default_mode?: string | null;
  allow: string[];
  deny: string[];
  ask: string[];
  base_mode: string;
  base_allow: string[];
}

export interface SharedContext {
  key: string;
  value: string;
  set_by_agent_id?: number | null;
  updated_at: string;
}

/* Thrown on a 401 so callers can distinguish "token rejected" from real errors and stay
 * quiet while the app re-prompts for a token. */
export class AuthError extends Error {
  constructor(message = "unauthorized") {
    super(message);
    this.name = "AuthError";
  }
}

/* Any non-2xx (other than 401); carries the HTTP status so callers can branch on 404 etc. */
export interface ApiError extends Error {
  status: number;
}

interface ApiOptions {
  method?: string;
  body?: unknown;
}

interface TrackOptions {
  attempts?: number;
  intervalMs?: number;
}

export interface ApiClient {
  api: <T>(path: string, opts?: ApiOptions) => Promise<T>;
  /* Poll GET /commands/{id} until it reaches done/failed; null if still running after the
   * budget (worker down or a very slow command). */
  trackCommand: (id: number, opts?: TrackOptions) => Promise<Command | null>;
}

export function createClient(token: string, onUnauthorized: () => void): ApiClient {
  async function api<T>(path: string, opts?: ApiOptions): Promise<T> {
    const hasBody = opts?.body !== undefined && opts?.body !== null;
    const res = await fetch(BASE + path, {
      method: opts?.method ?? (hasBody ? "POST" : "GET"),
      headers: {
        Authorization: `Bearer ${token}`,
        ...(hasBody ? { "Content-Type": "application/json" } : {}),
      },
      body: hasBody ? JSON.stringify(opts!.body) : undefined,
    });

    if (res.status === 401) {
      onUnauthorized();
      throw new AuthError();
    }
    if (!res.ok) {
      let detail: string = res.statusText;
      try {
        const j = await res.json();
        if (j && typeof j.detail !== "undefined") {
          detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
        }
      } catch {
        /* non-JSON error body; keep statusText */
      }
      const err = new Error(detail) as ApiError;
      err.status = res.status;
      throw err;
    }

    if (res.status === 204) return undefined as T;
    const text = await res.text();
    return (text ? JSON.parse(text) : undefined) as T;
  }

  async function trackCommand(id: number, opts?: TrackOptions): Promise<Command | null> {
    const attempts = opts?.attempts ?? 60;
    const intervalMs = opts?.intervalMs ?? 500;
    for (let i = 0; i < attempts; i++) {
      const cmd = await api<Command>(`/commands/${id}`);
      if (cmd.status === "done" || cmd.status === "failed") return cmd;
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    return null;
  }

  return { api, trackCommand };
}
