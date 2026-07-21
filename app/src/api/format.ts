/* Formatting + status helpers shared by the screens. Pure functions, no API access.
 * timeAgo is ported from frontend/lib/format.ts; the tone/colour mappers translate a raw
 * handler status string into the app's design-system vocabulary (BadgeTone for pills,
 * a ThemeColors key for log lines). */

import type { ThemeColors } from "../theme/tokens";
import type { BadgeTone } from "../state/AppState";

/* Compact relative time, e.g. "3m", "2h", "5d". "—" for empty. Timestamps from the API are
 * ISO UTC strings; new Date() parses them. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo`;
  return `${Math.floor(months / 12)}y`;
}

/* Local clock time (HH:MM:SS) for a log line. "—" for empty. */
export function clockTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

const LABELS: Record<string, string> = {
  paused_for_input: "Waiting",
  not_applicable: "N/A",
};

/* A tidy, human-readable label for a status string. */
export function statusLabel(status: string | null | undefined): string {
  const raw = (status ?? "").trim();
  if (!raw) return "—";
  const key = raw.toLowerCase();
  if (LABELS[key]) return LABELS[key];
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/* Map a raw handler status (agent status, checkmark status, CI status) to a badge tone in
 * the app's four-tone vocabulary. */
export function statusTone(status: string | null | undefined): BadgeTone {
  switch ((status ?? "").toLowerCase()) {
    case "pass":
    case "done":
    case "completed":
    case "approved":
    case "success":
      return "positive";
    case "fail":
    case "failed":
    case "blocked":
    case "rejected":
    case "error":
      return "danger";
    case "pending":
    case "queued":
    case "running":
    case "working":
    case "paused_for_input":
      return "warning";
    default:
      return "neutral";
  }
}

/* Pick a ThemeColors key for a log line, given its status. */
export function statusColor(status: string | null | undefined): keyof ThemeColors {
  switch (statusTone(status)) {
    case "positive":
      return "positive";
    case "danger":
      return "danger";
    case "warning":
      return "warning";
    default:
      return "textBody";
  }
}
