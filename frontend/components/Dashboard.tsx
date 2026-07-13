/* The Control Center shell: a left nav (Runs / Repositories / Agents / Approvals / Git
 * Servers / Activity / Shared) and the active section on the right, matching the design's
 * hub layout. Command feedback and load errors surface as banners at the top of main. */
"use client";

import { useDashboard, type Section } from "@/components/store";
import { RunsSection } from "@/components/sections/RunsSection";
import { RepositoriesSection } from "@/components/sections/RepositoriesSection";
import { AgentsSection } from "@/components/sections/AgentsSection";
import { SchedulesSection } from "@/components/sections/SchedulesSection";
import { ApprovalsSection } from "@/components/sections/ApprovalsSection";
import { GitServersSection } from "@/components/sections/GitServersSection";
import { ActivitySection } from "@/components/sections/ActivitySection";
import { SharedSection } from "@/components/sections/SharedSection";
import { LoginSection } from "@/components/sections/LoginSection";

interface NavDef {
  key: Section;
  label: string;
  count: (s: ReturnType<typeof useDashboard>) => number;
  accent?: (s: ReturnType<typeof useDashboard>) => boolean;
}

const NAV: NavDef[] = [
  {
    key: "runs",
    label: "Runs",
    count: (s) => s.agents.length,
    accent: (s) => s.agents.some((a) => a.status === "paused_for_input"),
  },
  { key: "repositories", label: "Repositories", count: (s) => s.projects.length },
  { key: "agents", label: "Agents", count: (s) => s.agents.length },
  { key: "schedules", label: "Schedules", count: (s) => s.schedules.length },
  { key: "approvals", label: "Approvals", count: (s) => s.approvals.length },
  { key: "servers", label: "Git Servers", count: (s) => s.hosts.length },
  { key: "activity", label: "Activity", count: (s) => s.commands.length },
  { key: "shared", label: "Shared", count: (s) => s.shared.context.length },
  {
    key: "login",
    label: "Claude Login",
    count: () => 0,
    // Draw the eye to it until Claude is logged in on the host this session.
    accent: (s) => s.claudeLogin.status !== "done",
  },
];

export function Dashboard({ onSignOut }: { onSignOut: () => void }) {
  const s = useDashboard();

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo" />
          Claude Monitor
        </div>
        {NAV.map((n) => {
          const c = n.count(s);
          const isAccent = n.accent?.(s) ?? false;
          return (
            <button
              key={n.key}
              className={`nav-item${s.section === n.key ? " active" : ""}`}
              onClick={() => s.setSection(n.key)}
            >
              <span>{n.label}</span>
              <span className="count" style={isAccent ? { color: "var(--lw-warning-fg)" } : undefined}>
                {c || ""}
              </span>
            </button>
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

        {s.section === "runs" ? (
          <RunsSection />
        ) : (
          <div className="main-scroll">
            {s.section === "repositories" && <RepositoriesSection />}
            {s.section === "agents" && <AgentsSection />}
            {s.section === "schedules" && <SchedulesSection />}
            {s.section === "approvals" && <ApprovalsSection />}
            {s.section === "servers" && <GitServersSection />}
            {s.section === "activity" && <ActivitySection />}
            {s.section === "shared" && <SharedSection />}
            {s.section === "login" && <LoginSection />}
          </div>
        )}
      </main>
    </div>
  );
}
