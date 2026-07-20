import type { ThemeColors } from "../theme/tokens";

/** Fixed prototype content, transcribed from the 2a design. */

export interface WaitingAgent {
  id: string;
  title: string;
  question: string;
  /** agt-7a1d is the one that clears from the list once answered. */
  clearsOnAnswer?: boolean;
}

export const waitingAgents: WaitingAgent[] = [
  {
    id: "agt-7a1d",
    title: "handler · migrate state to sqlite",
    question: '"Drop the legacy JSON store, or keep it as a read fallback?"',
    clearsOnAnswer: true,
  },
  {
    id: "agt-3e90",
    title: "wheatsite · fix build on node 22",
    question: '"Pin node 20 in CI, or patch esbuild?"',
  },
  {
    id: "agt-b241",
    title: "api-gateway · add rate limiting",
    question: '"429 body: JSON or plain text?"',
  },
];

export type CheckmarkStatus = "positive" | "danger";

export interface Checkmark {
  title: string;
  meta: string;
  status: CheckmarkStatus;
}

export const recentCheckmarks: Checkmark[] = [
  {
    title: "handler · add /agents endpoint",
    meta: "done — tests pass · 14m ago",
    status: "positive",
  },
  {
    title: "wheatsite · refactor router",
    meta: "failed — 2 tests · 1h ago",
    status: "danger",
  },
  {
    title: "dotfiles · port zsh config",
    meta: "done — 12 turns · 3h ago",
    status: "positive",
  },
];

export const quickReplyLabels = ["Drop it", "Keep as fallback", "Ask me later"];

export const projectOptions = ["handler", "wheatsite", "dotfiles", "api-gateway"];

/** Agent-detail log tab (fixed 7 rows). `color` picks a palette key. */
export interface DetailLogRow {
  t: string;
  msg: string;
  color: keyof ThemeColors;
}

export const detailLog: DetailLogRow[] = [
  { t: "14:02", msg: "paused — waiting for input", color: "warning" },
  { t: "13:57", msg: "checkmark updated", color: "textBody" },
  { t: "13:52", msg: "tool: bash — sqlite3 .schema", color: "textMuted" },
  { t: "13:48", msg: "tool: edit — store/sqlite.rs", color: "textMuted" },
  { t: "13:40", msg: "tool: bash — cargo test store", color: "textMuted" },
  { t: "13:29", msg: "checkmark updated", color: "textBody" },
  { t: "13:21", msg: "tool: read — store/json.rs", color: "textMuted" },
];

export interface DetailMetaRow {
  label: string;
  value: string;
}

export const detailMeta: DetailMetaRow[] = [
  { label: "Started", value: "41m ago" },
  { label: "Model", value: "claude-sonnet-4" },
  { label: "Turns", value: "21" },
  { label: "Tokens", value: "348k" },
];

/** Global log feed. `err` and `p` drive the All / handler / Errors filters. */
export interface LogEntry {
  t: string;
  id: string;
  p: string;
  msg: string;
  color: keyof ThemeColors;
  err: boolean;
}

export const allLog: LogEntry[] = [
  { t: "14:02:11", id: "agt-7a1d", p: "handler", msg: "paused — waiting for input", color: "warning", err: false },
  { t: "13:58:40", id: "agt-9c77", p: "handler", msg: "checkmark updated", color: "textBody", err: false },
  { t: "13:51:02", id: "agt-2d08", p: "handler", msg: "done — 34 turns, tests pass", color: "positive", err: false },
  { t: "13:44:19", id: "agt-e33a", p: "wheatsite", msg: "error — 2 tests failed", color: "danger", err: true },
  { t: "13:39:55", id: "agt-51f0", p: "dotfiles", msg: "spawned → dotfiles", color: "textBody", err: false },
  { t: "13:31:07", id: "agt-b241", p: "api-gateway", msg: "paused — waiting for input", color: "warning", err: false },
  { t: "13:18:44", id: "agt-9c77", p: "handler", msg: "tool: bash — cargo test", color: "textMuted", err: false },
  { t: "13:02:30", id: "agt-90bc", p: "dotfiles", msg: "done — 12 turns", color: "positive", err: false },
  { t: "12:57:12", id: "agt-51f0", p: "dotfiles", msg: "tool: edit — .zshrc", color: "textMuted", err: false },
  { t: "12:49:03", id: "agt-e33a", p: "wheatsite", msg: "checkmark updated", color: "textBody", err: false },
  { t: "12:40:38", id: "agt-b241", p: "api-gateway", msg: "spawned → api-gateway", color: "textBody", err: false },
];
