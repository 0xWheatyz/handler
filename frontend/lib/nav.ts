/* The left-nav map: one entry per section, each its own route/page. This is the single
 * source of truth shared by the sidebar (which renders the links) and the auth frame
 * (which seeds the store's active section from the URL on first load). Runs is the root. */
import type { Section } from "@/components/store";

export interface NavRoute {
  key: Section;
  href: string;
  label: string;
}

export const NAV_ROUTES: NavRoute[] = [
  { key: "runs", href: "/", label: "Runs" },
  { key: "repositories", href: "/repositories", label: "Repositories" },
  { key: "agents", href: "/agents", label: "Agents" },
  { key: "schedules", href: "/schedules", label: "Schedules" },
  { key: "approvals", href: "/approvals", label: "Approvals" },
  { key: "servers", href: "/servers", label: "Git Servers" },
  { key: "activity", href: "/activity", label: "Activity" },
  { key: "shared", href: "/shared", label: "Shared" },
  { key: "login", href: "/login", label: "Claude Login" },
];

/* Map a browser path back to its section key. Trailing slashes (Next emits them under
 * `trailingSlash: true`) are normalized away; anything unrecognized falls back to Runs. */
export function sectionFromPath(pathname: string): Section {
  const clean = pathname.replace(/\/+$/, "") || "/";
  return NAV_ROUTES.find((r) => r.href === clean)?.key ?? "runs";
}
