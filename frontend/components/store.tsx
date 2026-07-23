/* Dashboard state: one store owns the API client, the loaded data for every section,
 * the 5s polling loop, and all mutating actions. Control actions enqueue a command and
 * poll it to done/failed, surfacing the outcome in the command banner (`cmd`). */
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  AuthError,
  createClient,
  type Agent,
  type AgentEvent,
  type ApiError,
  type Approval,
  type Checkmark,
  type Command,
  type Host,
  type LogEntry,
  type Project,
  type Schedule,
  type SharedContext,
} from "@/lib/api";

export type Section =
  | "runs"
  | "repositories"
  | "agents"
  | "schedules"
  | "approvals"
  | "servers"
  | "activity"
  | "shared"
  | "login";

/* The claude web-login flow, driven through the login_start / login_submit commands.
 *  idle → starting → awaiting (have URL) → submitting → done | error */
export type ClaudeLoginStatus =
  | "idle"
  | "starting"
  | "awaiting"
  | "submitting"
  | "done"
  | "error";

export interface ClaudeLoginState {
  status: ClaudeLoginStatus;
  url: string;
  message: string;
}

export interface RunAgent extends Agent {}

export interface CmdState {
  text: string;
  error: boolean;
  busy: boolean;
}

const LOG_LIMIT = 100;
const POLL_MS = 5000;

interface StoreValue {
  section: Section;
  setSection: (s: Section) => void;

  projects: Project[];
  agents: RunAgent[]; // every agent across every project
  selectedProjectId: string;
  selectProject: (id: string) => void;

  // Runs inbox
  selectedRun: { projectId: string; name: string } | null;
  selectRun: (projectId: string, name: string) => void;
  checkmark: Checkmark | null;
  checkmarkMissing: boolean;
  log: LogEntry[];
  logOffset: number;
  pageLog: (dir: 1 | -1) => void;
  /* Headless run event stream for the selected run, oldest-first, appended by cursor
   * polls (empty for legacy tmux agents). */
  events: AgentEvent[];

  approvals: Approval[];
  hosts: Host[];
  commands: Command[];
  schedules: Schedule[];
  shared: { log: LogEntry[]; context: SharedContext[] };

  cmd: CmdState;
  lastError: string;
  loading: boolean;

  refresh: () => void;

  // actions
  spawnAgent: (body: SpawnBody) => Promise<boolean>;
  killAgent: (projectId: string, name: string) => Promise<void>;
  deleteAgent: (projectId: string, name: string) => Promise<void>;
  submitAnswer: (answer: string, resume: boolean) => Promise<boolean>;
  createProject: (b: NewProjectBody) => Promise<boolean>;
  updateProject: (id: string, b: Omit<ProjectBody, "id">) => Promise<boolean>;
  deleteProject: (id: string) => Promise<void>;
  syncProject: (id: string) => Promise<void>;
  submitApproval: (b: ApprovalBody) => Promise<void>;
  createHost: (b: HostBody) => Promise<boolean>;
  updateHost: (hostname: string, b: Omit<HostBody, "hostname">) => Promise<boolean>;
  deleteHost: (hostname: string) => Promise<void>;
  createSchedule: (projectId: string, b: ScheduleBody) => Promise<boolean>;
  updateSchedule: (id: number, b: Partial<ScheduleBody> & { enabled?: boolean }) => Promise<boolean>;
  deleteSchedule: (id: number) => Promise<void>;
  pollCi: () => Promise<void>;
  setSharedKey: (key: string, value: string) => Promise<boolean>;

  // Claude web-login
  claudeLogin: ClaudeLoginState;
  startClaudeLogin: () => Promise<void>;
  submitClaudeCode: (code: string) => Promise<boolean>;
  resetClaudeLogin: () => void;
}

export interface SpawnBody {
  name: string;
  role: string;
  placement: "worktree" | "subdir";
  worktree: string;
  subdir: string;
  task: string;
}
export interface ProjectBody {
  id: string;
  root_dir: string;
  git_remote: string;
  credential_ref: string;
}
/* New-project form. "server" mode = pick a configured git server + owner/name (Handler
 * derives the remote, picks the disk location, and clones); "manual" = the old fields. */
export interface NewProjectBody {
  mode: "server" | "manual";
  git_server: string;
  repo: string;
  id: string;
  root_dir: string;
  git_remote: string;
  credential_ref: string;
  /* Bootstrap tooling: after the clone, run an agent that writes + commits + pushes a
   * .mise.toml with a [tasks.test] task for the repo's stack. Needs a git remote. */
  init_mise: boolean;
}
export interface ScheduleBody {
  name_prefix: string;
  task: string;
  interval_seconds: number;
  role: string;
}
export interface ApprovalBody {
  branch: string;
  status: string;
  agent_name: string;
  sha: string;
  note: string;
}
export interface HostBody {
  hostname: string;
  forge_type: string;
  token_env_var: string;
  base_url: string;
  /* Write-only: encrypted at rest server-side, never echoed back. Blank = no change. */
  token: string;
  /* Create: mint a deploy keypair. Update: replace the existing one. */
  generate_ssh_key: boolean;
}

const Ctx = createContext<StoreValue | null>(null);

export function useDashboard(): StoreValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useDashboard outside provider");
  return v;
}

export function DashboardProvider({
  token,
  onUnauthorized,
  initialSection = "runs",
  children,
}: {
  token: string;
  onUnauthorized: () => void;
  /* Which section is on screen at mount, derived from the URL by the auth frame. The
   * provider lives in the root layout and mounts once, so this only seeds the first
   * poll; later navigation updates the section through setSection. */
  initialSection?: Section;
  children: ReactNode;
}) {
  const client = useMemo(() => createClient(token, onUnauthorized), [token, onUnauthorized]);
  const clientRef = useRef(client);
  clientRef.current = client;

  const [section, setSectionRaw] = useState<Section>(initialSection);
  const [projects, setProjects] = useState<Project[]>([]);
  const [agents, setAgents] = useState<RunAgent[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [selectedRun, setSelectedRun] = useState<{ projectId: string; name: string } | null>(null);
  const [checkmark, setCheckmark] = useState<Checkmark | null>(null);
  const [checkmarkMissing, setCheckmarkMissing] = useState(false);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [logOffset, setLogOffset] = useState(0);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const eventsRef = useRef<AgentEvent[]>([]);
  eventsRef.current = events;
  /* Bumped on every selectRun: an in-flight loadRun that resolves after the user picked
   * a different run must drop its writes, or run A's checkmark/log/events land on run
   * B's panel (the 5s tick keeps polls in flight constantly). */
  const runGenRef = useRef(0);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [hosts, setHosts] = useState<Host[]>([]);
  const [commands, setCommands] = useState<Command[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [shared, setShared] = useState<{ log: LogEntry[]; context: SharedContext[] }>({
    log: [],
    context: [],
  });
  const [cmd, setCmd] = useState<CmdState>({ text: "", error: false, busy: false });
  const [lastError, setLastError] = useState("");
  const [loading, setLoading] = useState(true);
  const [claudeLogin, setClaudeLogin] = useState<ClaudeLoginState>({
    status: "idle",
    url: "",
    message: "",
  });

  // Keep polling loop reading fresh values without re-subscribing every render.
  const sectionRef = useRef(section);
  sectionRef.current = section;
  const selectedProjectRef = useRef(selectedProjectId);
  selectedProjectRef.current = selectedProjectId;
  const selectedRunRef = useRef(selectedRun);
  selectedRunRef.current = selectedRun;
  const logOffsetRef = useRef(logOffset);
  logOffsetRef.current = logOffset;

  const swallow = (e: unknown) => {
    if (!(e instanceof AuthError)) setLastError((e as Error).message);
  };

  const loadProjects = useCallback(async () => {
    try {
      const ps = await clientRef.current.api<Project[]>("/projects");
      setProjects(ps);
      setLastError("");
      setSelectedProjectId((cur) => cur || (ps[0]?.id ?? ""));
    } catch (e) {
      swallow(e);
    }
  }, []);

  const loadAgents = useCallback(async (projectList: Project[]) => {
    try {
      const results = await Promise.all(
        projectList.map((p) =>
          clientRef.current
            .api<Agent[]>(`/projects/${encodeURIComponent(p.id)}/agents`)
            .catch(() => [] as Agent[]),
        ),
      );
      setAgents(results.flat());
    } catch (e) {
      swallow(e);
    }
  }, []);

  const loadRun = useCallback(async (projectId: string, name: string) => {
    const path = `/projects/${encodeURIComponent(projectId)}/agents/${encodeURIComponent(name)}`;
    const gen = runGenRef.current;
    const stale = () => gen !== runGenRef.current;
    try {
      const cm = await clientRef.current.api<Checkmark>(`${path}/checkmark`);
      if (stale()) return;
      setCheckmark(cm);
      setCheckmarkMissing(false);
    } catch (e) {
      if (e instanceof AuthError || stale()) return;
      if ((e as ApiError).status === 404) {
        setCheckmark(null);
        setCheckmarkMissing(true);
      } else swallow(e);
    }
    try {
      const entries = await clientRef.current.api<LogEntry[]>(
        `${path}/log?limit=${LOG_LIMIT}&offset=${logOffsetRef.current}`,
      );
      if (stale()) return;
      setLog(entries);
    } catch (e) {
      if (!stale()) swallow(e);
    }
    try {
      // Cursor poll: only events newer than what we already hold come back.
      const cur = eventsRef.current;
      const after = cur.length ? cur[cur.length - 1].id : 0;
      const fresh = await clientRef.current.api<AgentEvent[]>(
        `${path}/events?after_id=${after}&limit=500`,
      );
      if (stale() || fresh.length === 0) return;
      // Dedup by id at append time: overlapping polls for the same run can both fetch
      // from the same cursor; only genuinely-new rows may append.
      setEvents((prev) => {
        const last = prev.length ? prev[prev.length - 1].id : 0;
        const add = fresh.filter((e) => e.id > last);
        return add.length ? [...prev, ...add] : prev;
      });
    } catch (e) {
      if (!stale()) swallow(e);
    }
  }, []);

  const loadApprovals = useCallback(async (projectId: string) => {
    if (!projectId) {
      setApprovals([]);
      return;
    }
    try {
      setApprovals(
        await clientRef.current.api<Approval[]>(
          `/projects/${encodeURIComponent(projectId)}/approvals`,
        ),
      );
    } catch (e) {
      swallow(e);
    }
  }, []);

  const loadHosts = useCallback(async () => {
    try {
      setHosts(await clientRef.current.api<Host[]>("/hosts"));
    } catch (e) {
      swallow(e);
    }
  }, []);

  const loadCommands = useCallback(async () => {
    try {
      setCommands(await clientRef.current.api<Command[]>("/commands?limit=50"));
    } catch (e) {
      swallow(e);
    }
  }, []);

  const loadSchedules = useCallback(async () => {
    try {
      setSchedules(await clientRef.current.api<Schedule[]>("/schedules"));
    } catch (e) {
      swallow(e);
    }
  }, []);

  const loadShared = useCallback(async () => {
    try {
      const [logRows, context] = await Promise.all([
        clientRef.current.api<LogEntry[]>("/shared/log"),
        clientRef.current.api<SharedContext[]>("/shared/context"),
      ]);
      setShared({ log: logRows, context });
    } catch (e) {
      swallow(e);
    }
  }, []);

  /* One refresh cycle for whatever section is active (plus always-cheap projects/agents
   * so the nav counts and inbox stay live). */
  const tick = useCallback(async () => {
    const ps = await clientRef.current
      .api<Project[]>("/projects")
      .catch((e) => {
        swallow(e);
        return null;
      });
    if (ps) {
      setProjects(ps);
      setSelectedProjectId((cur) => cur || (ps[0]?.id ?? ""));
      await loadAgents(ps);
    }
    const s = sectionRef.current;
    const run = selectedRunRef.current;
    if (run) await loadRun(run.projectId, run.name);
    if (s === "approvals") await loadApprovals(selectedProjectRef.current);
    if (s === "servers") await loadHosts();
    if (s === "activity") await loadCommands();
    if (s === "schedules") await loadSchedules();
    if (s === "shared") await loadShared();
  }, [loadAgents, loadRun, loadApprovals, loadHosts, loadCommands, loadSchedules, loadShared]);

  // Initial load + polling loop. The first tick populates projects *and* agents (and the
  // active section) up front, so the Runs inbox is filled without waiting a poll interval.
  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      await tick();
      if (alive) setLoading(false);
    })();
    const id = setInterval(() => {
      if (!document.hidden) void tick();
    }, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [tick]);

  const setSection = useCallback(
    (s: Section) => {
      setSectionRaw(s);
      setCmd({ text: "", error: false, busy: false });
      if (s === "approvals") void loadApprovals(selectedProjectRef.current);
      if (s === "servers") void loadHosts();
      if (s === "activity") void loadCommands();
      if (s === "schedules") void loadSchedules();
      if (s === "shared") void loadShared();
    },
    [loadApprovals, loadHosts, loadCommands, loadSchedules, loadShared],
  );

  const selectProject = useCallback(
    (id: string) => {
      setSelectedProjectId(id);
      if (sectionRef.current === "approvals") void loadApprovals(id);
    },
    [loadApprovals],
  );

  const selectRun = useCallback(
    (projectId: string, name: string) => {
      runGenRef.current += 1; // invalidate any in-flight loadRun for the previous run
      setSelectedRun({ projectId, name });
      setLogOffset(0);
      logOffsetRef.current = 0;
      setCheckmark(null);
      setCheckmarkMissing(false);
      setLog([]);
      setEvents([]);
      eventsRef.current = [];
      void loadRun(projectId, name);
    },
    [loadRun],
  );

  const pageLog = useCallback(
    (dir: 1 | -1) => {
      const next = Math.max(0, logOffset + dir * LOG_LIMIT);
      if (next === logOffset) return;
      setLogOffset(next);
      logOffsetRef.current = next;
      const run = selectedRunRef.current;
      if (run) void loadRun(run.projectId, run.name);
    },
    [logOffset, loadRun],
  );

  const refresh = useCallback(() => {
    void tick();
  }, [tick]);

  // ---- control actions (enqueue + track) ----
  const enqueueAndTrack = useCallback(
    async (path: string, body: unknown, label: string): Promise<Command | null> => {
      setCmd({ text: `${label}: queued…`, error: false, busy: true });
      try {
        const command = await clientRef.current.api<Command>(path, { method: "POST", body });
        const final = await clientRef.current.trackCommand(command.id);
        if (!final) {
          setCmd({
            text: `${label}: still running (see Activity). Is the worker up?`,
            error: false,
            busy: false,
          });
          return null;
        }
        const ok = final.status === "done";
        const detail = final.error || (final.result ? JSON.stringify(final.result) : "");
        setCmd({
          text: `${label} ${ok ? "done" : "failed"}${detail ? " — " + detail : ""}`,
          error: !ok,
          busy: false,
        });
        return final;
      } catch (e) {
        if (e instanceof AuthError) return null;
        setCmd({ text: `${label} failed: ${(e as Error).message}`, error: true, busy: false });
        return null;
      }
    },
    [],
  );

  const spawnAgent = useCallback(
    async (f: SpawnBody) => {
      const body: Record<string, unknown> = {
        name: f.name.trim(),
        role: f.role || null,
        task: f.task.trim() || null,
      };
      if (f.placement === "worktree" && f.worktree.trim()) body.worktree = f.worktree.trim();
      if (f.placement === "subdir" && f.subdir.trim()) body.subdir = f.subdir.trim();
      const p = encodeURIComponent(selectedProjectRef.current);
      const final = await enqueueAndTrack(`/projects/${p}/agents/spawn`, body, `spawn ${body.name}`);
      await loadAgents(projects);
      return final?.status === "done";
    },
    [enqueueAndTrack, loadAgents, projects],
  );

  const killAgent = useCallback(
    async (projectId: string, name: string) => {
      const p = encodeURIComponent(projectId);
      await enqueueAndTrack(`/projects/${p}/agents/${encodeURIComponent(name)}/kill`, undefined, `kill ${name}`);
      await loadAgents(projects);
    },
    [enqueueAndTrack, loadAgents, projects],
  );

  const deleteAgent = useCallback(
    async (projectId: string, name: string) => {
      const p = encodeURIComponent(projectId);
      try {
        await clientRef.current.api(`/projects/${p}/agents/${encodeURIComponent(name)}`, {
          method: "DELETE",
        });
        setCmd({ text: `agent '${name}' row deleted`, error: false, busy: false });
        if (selectedRunRef.current?.name === name) setSelectedRun(null);
        await loadAgents(projects);
      } catch (e) {
        if (e instanceof AuthError) return;
        setCmd({ text: (e as Error).message, error: true, busy: false });
      }
    },
    [loadAgents, projects],
  );

  const submitAnswer = useCallback(
    async (answer: string, resume: boolean) => {
      const run = selectedRunRef.current;
      if (!run) return false;
      const path = `/projects/${encodeURIComponent(run.projectId)}/agents/${encodeURIComponent(run.name)}`;
      try {
        await clientRef.current.api(`${path}/answer`, { method: "POST", body: { answer } });
        if (resume) {
          await enqueueAndTrack(`${path}/resume`, { answer }, "resume");
        } else {
          setCmd({ text: "Answer saved (agent still paused).", error: false, busy: false });
        }
        await loadAgents(projects);
        await loadRun(run.projectId, run.name);
        return true;
      } catch (e) {
        if (e instanceof AuthError) return false;
        setCmd({ text: (e as Error).message, error: true, busy: false });
        return false;
      }
    },
    [enqueueAndTrack, loadAgents, loadRun, projects],
  );

  const createProject = useCallback(
    async (b: NewProjectBody) => {
      try {
        const body: Record<string, unknown> =
          b.mode === "server"
            ? {
                git_server: b.git_server,
                repo: b.repo.trim(),
                id: b.id.trim() || null,
                credential_ref: b.credential_ref.trim() || null,
                init_mise: b.init_mise,
              }
            : {
                id: b.id.trim(),
                root_dir: b.root_dir.trim(),
                git_remote: b.git_remote.trim() || null,
                credential_ref: b.credential_ref.trim() || null,
                init_mise: b.init_mise,
              };
        const created = await clientRef.current.api<Project>("/projects", {
          method: "POST",
          body,
        });
        await loadProjects();
        // Server mode enqueues a clone; follow it so the operator sees the repo land.
        if (created.sync_command_id != null) {
          setCmd({ text: `repository '${created.id}': cloning…`, error: false, busy: true });
          const final = await clientRef.current.trackCommand(created.sync_command_id);
          if (!final) {
            setCmd({
              text: `repository '${created.id}' registered; clone still running (see Activity). Is the worker up?`,
              error: false,
              busy: false,
            });
          } else if (final.status === "done") {
            setCmd({
              text: `repository '${created.id}' registered and cloned`,
              error: false,
              busy: false,
            });
          } else {
            setCmd({
              text: `repository '${created.id}' registered but the clone failed — ${final.error ?? ""}`,
              error: true,
              busy: false,
            });
          }
        } else {
          setCmd({ text: `repository '${created.id}' registered`, error: false, busy: false });
        }
        // "Initialize mise": follow the bootstrap agent's launch so the operator knows a
        // .mise.toml is being written, committed, and pushed for them.
        if (created.mise_init_command_id != null) {
          setCmd({
            text: `repository '${created.id}': launching a mise-init agent to create .mise.toml…`,
            error: false,
            busy: true,
          });
          const mise = await clientRef.current.trackCommand(created.mise_init_command_id);
          if (!mise) {
            setCmd({
              text: `repository '${created.id}' registered; mise-init still starting (see Activity). Is the worker up?`,
              error: false,
              busy: false,
            });
          } else if (mise.status === "done") {
            setCmd({
              text: `repository '${created.id}' registered; a mise-init agent is now writing, committing, and pushing .mise.toml (watch it in Runs).`,
              error: false,
              busy: false,
            });
          } else {
            setCmd({
              text: `repository '${created.id}' registered but the mise-init agent failed to launch — ${mise.error ?? ""}`,
              error: true,
              busy: false,
            });
          }
        }
        return true;
      } catch (e) {
        if (e instanceof AuthError) return false;
        setCmd({ text: (e as Error).message, error: true, busy: false });
        return false;
      }
    },
    [loadProjects],
  );

  const syncProject = useCallback(
    async (id: string) => {
      await enqueueAndTrack(`/projects/${encodeURIComponent(id)}/sync`, undefined, `pull ${id}`);
    },
    [enqueueAndTrack],
  );

  const updateProject = useCallback(
    async (id: string, b: Omit<ProjectBody, "id">) => {
      try {
        await clientRef.current.api(`/projects/${encodeURIComponent(id)}`, {
          method: "PATCH",
          body: {
            root_dir: b.root_dir.trim(),
            git_remote: b.git_remote.trim() || null,
            credential_ref: b.credential_ref.trim() || null,
          },
        });
        setCmd({ text: `repository '${id}' updated`, error: false, busy: false });
        await loadProjects();
        return true;
      } catch (e) {
        if (e instanceof AuthError) return false;
        setCmd({ text: (e as Error).message, error: true, busy: false });
        return false;
      }
    },
    [loadProjects],
  );

  const deleteProject = useCallback(
    async (id: string) => {
      try {
        await clientRef.current.api(`/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
        setCmd({ text: `repository '${id}' removed`, error: false, busy: false });
        setSelectedProjectId((cur) => (cur === id ? "" : cur));
        await loadProjects();
      } catch (e) {
        if (e instanceof AuthError) return;
        setCmd({ text: (e as Error).message, error: true, busy: false });
      }
    },
    [loadProjects],
  );

  const submitApproval = useCallback(
    async (b: ApprovalBody) => {
      const p = encodeURIComponent(selectedProjectRef.current);
      await enqueueAndTrack(
        `/projects/${p}/approvals`,
        {
          branch: b.branch.trim(),
          status: b.status,
          agent_name: b.agent_name.trim() || null,
          sha: b.sha.trim() || null,
          note: b.note.trim() || null,
        },
        `${b.status} ${b.branch}`,
      );
      await loadApprovals(selectedProjectRef.current);
    },
    [enqueueAndTrack, loadApprovals],
  );

  const createHost = useCallback(
    async (b: HostBody) => {
      try {
        await clientRef.current.api("/hosts", {
          method: "POST",
          body: {
            hostname: b.hostname.trim(),
            forge_type: b.forge_type,
            token_env_var: b.token_env_var.trim() || null,
            base_url: b.base_url.trim() || null,
            token: b.token.trim() || null,
            generate_ssh_key: b.generate_ssh_key,
          },
        });
        setCmd({ text: `git server '${b.hostname}' added`, error: false, busy: false });
        await loadHosts();
        return true;
      } catch (e) {
        if (e instanceof AuthError) return false;
        setCmd({ text: (e as Error).message, error: true, busy: false });
        return false;
      }
    },
    [loadHosts],
  );

  const updateHost = useCallback(
    async (hostname: string, b: Omit<HostBody, "hostname">) => {
      try {
        const body: Record<string, unknown> = {
          forge_type: b.forge_type,
          token_env_var: b.token_env_var.trim() || null,
          base_url: b.base_url.trim() || null,
        };
        if (b.token.trim()) body.token = b.token.trim();
        if (b.generate_ssh_key) body.regenerate_ssh_key = true;
        await clientRef.current.api(`/hosts/${encodeURIComponent(hostname)}`, {
          method: "PATCH",
          body,
        });
        setCmd({ text: `git server '${hostname}' updated`, error: false, busy: false });
        await loadHosts();
        return true;
      } catch (e) {
        if (e instanceof AuthError) return false;
        setCmd({ text: (e as Error).message, error: true, busy: false });
        return false;
      }
    },
    [loadHosts],
  );

  const createSchedule = useCallback(
    async (projectId: string, b: ScheduleBody) => {
      try {
        await clientRef.current.api(`/projects/${encodeURIComponent(projectId)}/schedules`, {
          method: "POST",
          body: {
            name_prefix: b.name_prefix.trim(),
            task: b.task.trim(),
            interval_seconds: b.interval_seconds,
            role: b.role || null,
          },
        });
        setCmd({
          text: `schedule '${b.name_prefix}' created — first run on the worker's next pass`,
          error: false,
          busy: false,
        });
        await loadSchedules();
        return true;
      } catch (e) {
        if (e instanceof AuthError) return false;
        setCmd({ text: (e as Error).message, error: true, busy: false });
        return false;
      }
    },
    [loadSchedules],
  );

  const updateSchedule = useCallback(
    async (id: number, b: Partial<ScheduleBody> & { enabled?: boolean }) => {
      try {
        await clientRef.current.api(`/schedules/${id}`, { method: "PATCH", body: b });
        await loadSchedules();
        return true;
      } catch (e) {
        if (e instanceof AuthError) return false;
        setCmd({ text: (e as Error).message, error: true, busy: false });
        return false;
      }
    },
    [loadSchedules],
  );

  const deleteSchedule = useCallback(
    async (id: number) => {
      try {
        await clientRef.current.api(`/schedules/${id}`, { method: "DELETE" });
        setCmd({ text: `schedule ${id} removed`, error: false, busy: false });
        await loadSchedules();
      } catch (e) {
        if (e instanceof AuthError) return;
        setCmd({ text: (e as Error).message, error: true, busy: false });
      }
    },
    [loadSchedules],
  );

  const deleteHost = useCallback(
    async (hostname: string) => {
      try {
        await clientRef.current.api(`/hosts/${encodeURIComponent(hostname)}`, { method: "DELETE" });
        setCmd({ text: `git server '${hostname}' removed`, error: false, busy: false });
        await loadHosts();
      } catch (e) {
        if (e instanceof AuthError) return;
        setCmd({ text: (e as Error).message, error: true, busy: false });
      }
    },
    [loadHosts],
  );

  const pollCi = useCallback(async () => {
    await enqueueAndTrack("/poll-ci", undefined, "poll-ci (all projects)");
    await loadCommands();
  }, [enqueueAndTrack, loadCommands]);

  // ---- claude web-login (login_start / login_submit through the command queue) ----
  const startClaudeLogin = useCallback(async () => {
    setClaudeLogin({
      status: "starting",
      url: "",
      message: "Opening `claude /login` in the control container and selecting the subscription account…",
    });
    try {
      const command = await clientRef.current.api<Command>("/login/start", { method: "POST" });
      // login_start boots claude, drives the menu, and scrapes the URL — allow ~90s
      // (worker claim latency + boot waits + URL timeout).
      const final = await clientRef.current.trackCommand(command.id, { attempts: 180 });
      if (!final) {
        setClaudeLogin({
          status: "error",
          url: "",
          message: "Still starting (see Activity). Is the control worker running?",
        });
        return;
      }
      if (final.status !== "done") {
        setClaudeLogin({ status: "error", url: "", message: final.error || "Failed to start login." });
        return;
      }
      const url = final.result && typeof final.result.url === "string" ? final.result.url : "";
      if (!url) {
        setClaudeLogin({ status: "error", url: "", message: "No login URL was returned by claude." });
        return;
      }
      setClaudeLogin({
        status: "awaiting",
        url,
        message: "Authorize in the window below (or open it in a new tab), then paste the code claude gives you.",
      });
    } catch (e) {
      if (e instanceof AuthError) return;
      setClaudeLogin({ status: "error", url: "", message: (e as Error).message });
    }
  }, []);

  const submitClaudeCode = useCallback(async (code: string) => {
    const trimmed = code.trim();
    if (!trimmed) return false;
    setClaudeLogin((c) => ({ ...c, status: "submitting", message: "Submitting the authorization code…" }));
    try {
      const command = await clientRef.current.api<Command>("/login/submit", {
        method: "POST",
        body: { code: trimmed },
      });
      const final = await clientRef.current.trackCommand(command.id, { attempts: 60 });
      if (!final) {
        setClaudeLogin((c) => ({
          ...c,
          status: "awaiting",
          message: "Submit still running (see Activity). Is the control worker running?",
        }));
        return false;
      }
      if (final.status === "done") {
        setClaudeLogin({
          status: "done",
          url: "",
          message: "Claude Code is now logged in on the host — new agents will use this account.",
        });
        return true;
      }
      setClaudeLogin((c) => ({
        ...c,
        status: "awaiting",
        message: final.error || "Login was not confirmed. Re-check the code, or restart the flow.",
      }));
      return false;
    } catch (e) {
      if (e instanceof AuthError) return false;
      setClaudeLogin((c) => ({ ...c, status: "awaiting", message: (e as Error).message }));
      return false;
    }
  }, []);

  const resetClaudeLogin = useCallback(() => {
    setClaudeLogin({ status: "idle", url: "", message: "" });
  }, []);

  const setSharedKey = useCallback(
    async (key: string, value: string) => {
      try {
        await clientRef.current.api(`/shared/context/${encodeURIComponent(key)}`, {
          method: "PUT",
          body: { value },
        });
        setCmd({ text: `shared context '${key}' set`, error: false, busy: false });
        await loadShared();
        return true;
      } catch (e) {
        if (e instanceof AuthError) return false;
        setCmd({ text: (e as Error).message, error: true, busy: false });
        return false;
      }
    },
    [loadShared],
  );

  const value: StoreValue = {
    section,
    setSection,
    projects,
    agents,
    selectedProjectId,
    selectProject,
    selectedRun,
    selectRun,
    checkmark,
    checkmarkMissing,
    log,
    logOffset,
    pageLog,
    events,
    approvals,
    hosts,
    commands,
    schedules,
    shared,
    cmd,
    lastError,
    loading,
    refresh,
    spawnAgent,
    killAgent,
    deleteAgent,
    submitAnswer,
    createProject,
    updateProject,
    deleteProject,
    syncProject,
    submitApproval,
    createHost,
    updateHost,
    deleteHost,
    createSchedule,
    updateSchedule,
    deleteSchedule,
    pollCi,
    setSharedKey,
    claudeLogin,
    startClaudeLogin,
    submitClaudeCode,
    resetClaudeLogin,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
