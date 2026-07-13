/* Formatting + status helpers shared by the UI. Pure functions, no API access.
 *
 * NOTE: this file lives under frontend/lib/, which the repo's top-level .gitignore used to
 * swallow (a broad `lib/` rule) — it is now un-ignored (see .gitignore) so the source ships
 * and `npm run build` works from a fresh clone. The *built* export under
 * src/handler/api/static/ is still what the Python package serves. */

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

/* Map a raw handler status string (agent status, gate status, CI status) to a badge tone. */
export function statusTone(status: string | null | undefined): Tone {
  switch ((status ?? "").toLowerCase()) {
    case "pass":
    case "done":
    case "completed":
    case "approved":
    case "success":
      return "success";
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
    case "not_applicable":
    case "unknown":
    case "":
      return "neutral";
    default:
      return "info";
  }
}

const LABELS: Record<string, string> = {
  paused_for_input: "Needs input",
  not_applicable: "N/A",
};

/* A tidy, human-readable label for a status string. */
export function statusLabel(status: string | null | undefined): string {
  const raw = (status ?? "").trim();
  if (!raw) return "—";
  const key = raw.toLowerCase();
  if (LABELS[key]) return LABELS[key];
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/* Full local date + time, e.g. "Jul 13, 2026, 2:04 PM". "—" for empty. */
export function fmtFull(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/* First 7 chars of a commit sha. "—" for empty. */
export function shortSha(sha: string | null | undefined): string {
  if (!sha) return "—";
  return sha.slice(0, 7);
}

/* Compact relative time, e.g. "3m", "2h", "5d". "—" for empty. */
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
