import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AuthError,
  createClient,
  type Agent,
  type ApiClient,
  type ApiError,
  type Checkmark,
  type LogEntry,
  type Project,
} from "../api/client";
import { statusLabel, statusTone, timeAgo } from "../api/format";
import { useServerConfig } from "./ServerConfig";

/**
 * Data-driven fleet store. Keeps the prototype's screen-swap navigation (a single
 * `screen` value rather than a nav stack) so the screens change minimally, but every
 * value now comes from the live Handler API via the client built from ServerConfig.
 *
 * The store polls /projects → agents → checkmarks → logs on a 10s cadence, derives the
 * fleet view-models (waiting list, recent checkmarks, counts, merged log), and exposes the
 * three mutations the UI needs (answer+resume, spawn, kill). A 401 anywhere clears the
 * stored config (routing back to ConnectScreen) via the client's onUnauthorized hook.
 */

export type Screen =
  | "connect"
  | "fleet"
  | "detail"
  | "answer"
  | "spawn"
  | "log"
  | "settings";

export type DetailTab = "state" | "log";
export type BadgeTone = "neutral" | "positive" | "warning" | "danger";
export type RecentTone = "positive" | "danger";

/** An agent waiting on the operator — either an open checkmark question or a paused status. */
export interface WaitingItem {
  project: string;
  name: string;
  question: string;
  logEntryId: number | null;
}

/** A recent checkmark row on the fleet screen. */
export interface RecentItem {
  key: string;
  project: string;
  name: string;
  title: string;
  meta: string;
  tone: RecentTone;
  checkpointAt: string;
}

/** One merged global-log line. */
export interface GlobalLogItem {
  key: string;
  project: string;
  name: string;
  createdAt: string;
  msg: string;
  status: string;
  ciStatus: string;
  err: boolean;
}

interface Selected {
  project: string;
  name: string;
}

interface AppStateValue {
  // Navigation.
  screen: Screen;
  detailTab: DetailTab;
  logFilter: string;
  go: (screen: Screen) => void;
  setDetailTab: (tab: DetailTab) => void;
  setLogFilter: (f: string) => void;
  openDetail: (project: string, name: string) => void;
  openAnswer: (project: string, name: string) => void;

  // Fleet data.
  loading: boolean;
  error: string | null;
  projects: Project[];
  waiting: WaitingItem[];
  recent: RecentItem[];
  counts: { running: number; waiting: number; done: number };
  globalLog: GlobalLogItem[];
  refresh: () => Promise<void>;

  // Selected agent (detail / answer screens).
  selectedAgent: Agent | null;
  selectedCheckmark: Checkmark | null;
  selectedLog: LogEntry[];

  // Mutations.
  sendAnswer: (text: string) => Promise<{ resumed: boolean; note?: string }>;
  spawn: (project: string, task: string) => Promise<void>;
  kill: (project: string, name: string) => Promise<void>;
}

const AppStateContext = createContext<AppStateValue | null>(null);

const enc = encodeURIComponent;
const agentKey = (project: string, name: string) => `${project}/${name}`;

function isApiError(e: unknown): e is ApiError {
  return e instanceof Error && typeof (e as ApiError).status === "number";
}

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message || "request failed";
  return String(e);
}

function isErrorStatus(status: string | null | undefined): boolean {
  const s = (status ?? "").toLowerCase();
  return s === "failed" || s === "error" || s === "fail";
}

/** Derive an agent name: a slug of the first few task words + 4 random hex chars. */
function deriveAgentName(task: string): string {
  const words = task
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 4);
  const slug = words.join("-") || "agent";
  const hex = Math.floor(Math.random() * 0x10000)
    .toString(16)
    .padStart(4, "0");
  return `${slug}-${hex}`;
}

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const { config, clear } = useServerConfig();

  // Fleet data.
  const [projects, setProjects] = useState<Project[]>([]);
  const [agentsByProject, setAgentsByProject] = useState<Record<string, Agent[]>>({});
  const [checkmarks, setCheckmarks] = useState<Record<string, Checkmark | null>>({});
  const [logsByAgent, setLogsByAgent] = useState<Record<string, LogEntry[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Navigation.
  const [screen, setScreen] = useState<Screen>("fleet");
  const [detailTab, setDetailTab] = useState<DetailTab>("state");
  const [logFilter, setLogFilter] = useState<string>("all");
  const [selected, setSelected] = useState<Selected | null>(null);

  const resetData = useCallback(() => {
    setProjects([]);
    setAgentsByProject({});
    setCheckmarks({});
    setLogsByAgent({});
    setSelected(null);
    setError(null);
  }, []);

  // The client is rebuilt whenever the endpoint/token change. A stale 401 clears local
  // data and drops the stored config, which routes the app back to ConnectScreen.
  const client = useMemo<ApiClient | null>(() => {
    if (!config) return null;
    return createClient(config.endpoint, config.token, () => {
      resetData();
      setScreen("fleet");
      void clear();
    });
  }, [config, clear, resetData]);

  const refresh = useCallback(async () => {
    if (!client) return;
    try {
      setError(null);
      const projs = await client.api<Project[]>("/projects");

      // Per-agent/per-project sub-requests are isolated: one flaky agent (a 500 on
      // its log, say) must not blank the whole fleet. A rejected AuthError still
      // propagates via onUnauthorized inside the client; here we just record the
      // failure for that one item and keep the rest of the fleet rendering.
      const agentLists = await Promise.all(
        projs.map((p) =>
          client
            .api<Agent[]>(`/projects/${enc(p.id)}/agents`)
            .then((list) => [p.id, list] as const)
            .catch((e) => {
              if (e instanceof AuthError) throw e;
              return [p.id, [] as Agent[]] as const;
            }),
        ),
      );

      const flat: { project: string; agent: Agent }[] = [];
      const abp: Record<string, Agent[]> = {};
      for (const [pid, list] of agentLists) {
        abp[pid] = list;
        for (const a of list) flat.push({ project: pid, agent: a });
      }

      const cmEntries = await Promise.all(
        flat.map(async ({ project, agent }) => {
          const key = agentKey(project, agent.name);
          try {
            const cm = await client.api<Checkmark>(
              `/projects/${enc(project)}/agents/${enc(agent.name)}/checkmark`,
            );
            return [key, cm] as const;
          } catch (e) {
            if (e instanceof AuthError) throw e;
            // 404 = no checkmark yet; any other error = leave it absent this cycle.
            return [key, null] as const;
          }
        }),
      );
      const cmMap: Record<string, Checkmark | null> = {};
      for (const [k, v] of cmEntries) cmMap[k] = v;

      const logEntries = await Promise.all(
        flat.map(async ({ project, agent }) => {
          const key = agentKey(project, agent.name);
          try {
            const log = await client.api<LogEntry[]>(
              `/projects/${enc(project)}/agents/${enc(agent.name)}/log`,
            );
            return [key, log] as const;
          } catch (e) {
            if (e instanceof AuthError) throw e;
            return [key, [] as LogEntry[]] as const;
          }
        }),
      );
      const logMap: Record<string, LogEntry[]> = {};
      for (const [k, v] of logEntries) logMap[k] = v;

      setProjects(projs);
      setAgentsByProject(abp);
      setCheckmarks(cmMap);
      setLogsByAgent(logMap);
    } catch (e) {
      if (e instanceof AuthError) return; // handled by onUnauthorized
      setError(errMessage(e));
    } finally {
      setLoading(false);
    }
  }, [client]);

  // Initial load + 10s poll while mounted; re-runs when the client (endpoint/token) changes.
  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;
  useEffect(() => {
    if (!client) return;
    setLoading(true);
    void refreshRef.current();
    const id = setInterval(() => {
      void refreshRef.current();
    }, 10000);
    return () => clearInterval(id);
  }, [client]);

  // ---- Derived view-models -------------------------------------------------
  const waiting = useMemo<WaitingItem[]>(() => {
    const out: WaitingItem[] = [];
    for (const [pid, list] of Object.entries(agentsByProject)) {
      for (const a of list) {
        const cm = checkmarks[agentKey(pid, a.name)] ?? null;
        const hasQuestion = !!(cm && cm.open_question);
        const paused = a.status.toLowerCase() === "paused_for_input";
        if (hasQuestion || paused) {
          out.push({
            project: pid,
            name: a.name,
            question:
              cm?.open_question?.trim() || "Agent is paused, waiting for input.",
            logEntryId: cm?.log_entry_id ?? null,
          });
        }
      }
    }
    return out;
  }, [agentsByProject, checkmarks]);

  const recent = useMemo<RecentItem[]>(() => {
    const rows: RecentItem[] = [];
    for (const [pid, list] of Object.entries(agentsByProject)) {
      for (const a of list) {
        const cm = checkmarks[agentKey(pid, a.name)];
        if (!cm) continue;
        rows.push({
          key: agentKey(pid, a.name),
          project: pid,
          name: a.name,
          title: `${pid} · ${a.name}`,
          meta: `${statusLabel(cm.status).toLowerCase()} — tests ${statusLabel(
            cm.tests_status,
          ).toLowerCase()} · ${timeAgo(cm.checkpoint_at)}`,
          tone: statusTone(cm.status) === "danger" ? "danger" : "positive",
          checkpointAt: cm.checkpoint_at,
        });
      }
    }
    rows.sort(
      (a, b) =>
        new Date(b.checkpointAt).getTime() - new Date(a.checkpointAt).getTime(),
    );
    return rows;
  }, [agentsByProject, checkmarks]);

  const counts = useMemo(() => {
    let running = 0;
    let done = 0;
    for (const list of Object.values(agentsByProject)) {
      for (const a of list) {
        const s = a.status.toLowerCase();
        if (s === "working" || s === "running") running++;
        else if (s === "done" || s === "failed") done++;
      }
    }
    return { running, waiting: waiting.length, done };
  }, [agentsByProject, waiting]);

  const globalLog = useMemo<GlobalLogItem[]>(() => {
    const rows: GlobalLogItem[] = [];
    for (const [pid, list] of Object.entries(agentsByProject)) {
      for (const a of list) {
        const entries = logsByAgent[agentKey(pid, a.name)] ?? [];
        for (const e of entries) {
          rows.push({
            key: `${pid}/${a.name}/${e.id}`,
            project: pid,
            name: a.name,
            createdAt: e.created_at,
            msg: e.summary?.trim() || statusLabel(e.status),
            status: e.status,
            ciStatus: e.ci_status,
            err: isErrorStatus(e.status) || isErrorStatus(e.ci_status),
          });
        }
      }
    }
    rows.sort(
      (a, b) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );
    return rows;
  }, [agentsByProject, logsByAgent]);

  // ---- Selected agent ------------------------------------------------------
  const selectedAgent = useMemo<Agent | null>(() => {
    if (!selected) return null;
    return (
      (agentsByProject[selected.project] ?? []).find(
        (a) => a.name === selected.name,
      ) ?? null
    );
  }, [selected, agentsByProject]);

  const selectedCheckmark = selected
    ? checkmarks[agentKey(selected.project, selected.name)] ?? null
    : null;
  const selectedLog = selected
    ? logsByAgent[agentKey(selected.project, selected.name)] ?? []
    : [];

  // ---- Navigation helpers --------------------------------------------------
  const openDetail = useCallback((project: string, name: string) => {
    setSelected({ project, name });
    setDetailTab("state");
    setScreen("detail");
  }, []);

  const openAnswer = useCallback((project: string, name: string) => {
    setSelected({ project, name });
    setScreen("answer");
  }, []);

  // ---- Mutations -----------------------------------------------------------
  const sendAnswer = useCallback(
    async (text: string): Promise<{ resumed: boolean; note?: string }> => {
      if (!client || !selected) throw new Error("no agent selected");
      const cm = checkmarks[agentKey(selected.project, selected.name)] ?? null;
      const base = `/projects/${enc(selected.project)}/agents/${enc(selected.name)}`;

      await client.api(`${base}/answer`, {
        body: {
          answer: text,
          ...(cm?.log_entry_id ? { log_entry_id: cm.log_entry_id } : {}),
        },
      });

      // Resume is admin-only: a valid non-admin token 403s (or 401 with allow401 set) but
      // the answer is already saved, so surface a soft note instead of failing.
      try {
        await client.api(`${base}/resume`, { body: {}, allow401: true });
      } catch (e) {
        if (isApiError(e) && (e.status === 401 || e.status === 403)) {
          await refresh();
          return {
            resumed: false,
            note: "answer saved — resume needs the admin token",
          };
        }
        throw e;
      }
      await refresh();
      return { resumed: true };
    },
    [client, selected, checkmarks, refresh],
  );

  const spawn = useCallback(
    async (project: string, task: string) => {
      if (!client) throw new Error("not connected");
      const name = deriveAgentName(task);
      await client.api(`/projects/${enc(project)}/agents/spawn`, {
        body: { name, ...(task.trim() ? { task: task.trim() } : {}) },
      });
      await refresh();
    },
    [client, refresh],
  );

  const kill = useCallback(
    async (project: string, name: string) => {
      if (!client) throw new Error("not connected");
      await client.api(`/projects/${enc(project)}/agents/${enc(name)}/kill`, {
        method: "POST",
      });
      await refresh();
    },
    [client, refresh],
  );

  const value = useMemo<AppStateValue>(
    () => ({
      screen,
      detailTab,
      logFilter,
      go: setScreen,
      setDetailTab,
      setLogFilter,
      openDetail,
      openAnswer,

      loading,
      error,
      projects,
      waiting,
      recent,
      counts,
      globalLog,
      refresh,

      selectedAgent,
      selectedCheckmark,
      selectedLog,

      sendAnswer,
      spawn,
      kill,
    }),
    [
      screen,
      detailTab,
      logFilter,
      openDetail,
      openAnswer,
      loading,
      error,
      projects,
      waiting,
      recent,
      counts,
      globalLog,
      refresh,
      selectedAgent,
      selectedCheckmark,
      selectedLog,
      sendAnswer,
      spawn,
      kill,
    ],
  );

  return (
    <AppStateContext.Provider value={value}>
      {children}
    </AppStateContext.Provider>
  );
}

export function useAppState(): AppStateValue {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState must be used within AppStateProvider");
  return ctx;
}
