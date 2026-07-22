/* The Control Center shell: a left nav (Runs / Repositories / Agents / Approvals / Git
 * Servers / Activity / Shared / Claude Login) and the active route's page on the right,
 * matching the design's hub layout. Each nav item is a real route, so pages are modular
 * and independently loadable; this shell lives in the root layout and persists across
 * navigation, keeping the store, polling loop, and auth alive between pages. Command
 * feedback and load errors surface as banners at the top of main. */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { useDashboard } from "@/components/store";
import { NAV_ROUTES, sectionFromPath } from "@/lib/nav";
import type { Section } from "@/components/store";

type Store = ReturnType<typeof useDashboard>;

/* Per-section nav badge: the count on the right and whether it should draw the eye. Keyed
 * by section so the route table in lib/nav stays free of store-shaped logic. */
const BADGES: Partial<Record<Section, { count: (s: Store) => number; accent?: (s: Store) => boolean }>> = {
  runs: {
    count: (s) => s.agents.length,
    accent: (s) => s.agents.some((a) => a.status === "paused_for_input"),
  },
  repositories: { count: (s) => s.projects.length },
  agents: { count: (s) => s.agents.length },
  schedules: { count: (s) => s.schedules.length },
  approvals: { count: (s) => s.approvals.length },
  servers: { count: (s) => s.hosts.length },
  activity: { count: (s) => s.commands.length },
  shared: { count: (s) => s.shared.context.length },
  login: {
    count: () => 0,
    // Draw the eye to it until Claude is logged in on the host this session.
    accent: (s) => s.claudeLogin.status !== "done",
  },
};

export function Shell({ onSignOut, children }: { onSignOut: () => void; children: React.ReactNode }) {
  const s = useDashboard();
  const pathname = usePathname();
  const active = sectionFromPath(pathname);

  // Tell the store which section is on screen so its polling loop fetches the right data.
  const { setSection } = s;
  useEffect(() => {
    setSection(active);
  }, [active, setSection]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo" />
          Claude Monitor
        </div>
        {NAV_ROUTES.map((n) => {
          const badge = BADGES[n.key];
          const c = badge?.count(s) ?? 0;
          const isAccent = badge?.accent?.(s) ?? false;
          return (
            <Link
              key={n.key}
              href={n.href}
              className={`nav-item${active === n.key ? " active" : ""}`}
            >
              <span>{n.label}</span>
              <span className="count" style={isAccent ? { color: "var(--lw-warning-fg)" } : undefined}>
                {c || ""}
              </span>
            </Link>
          );
        })}
        <div className="sidebar-spacer" />
        <div className="sidebar-foot">
          <button className="nav-item" onClick={s.refresh} title="Refresh now">
            <span>Refresh</span>
            <span className="count">↻</span>
          </button>
          <button className="nav-item" onClick={onSignOut} title="Sign out / change token">
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      <main className="main">
        {s.cmd.text && (
          <p className={`banner ${s.cmd.error ? "err" : "ok"}`} style={{ marginTop: 16 }}>
            {s.cmd.text}
          </p>
        )}
        {s.lastError && (
          <p className="banner err" style={{ marginTop: 12 }}>
            {s.lastError}
          </p>
        )}
        {children}
      </main>
    </div>
  );
}
