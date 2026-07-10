/* Activity — the control-command queue: every enqueued action and its status
 * (queued → running → done/failed). The audit log of what the dashboard triggered. */
"use client";

import { useDashboard } from "@/components/store";
import { Button, StatusBadge } from "@/components/ui";
import { fmtFull } from "@/lib/format";

export function ActivitySection() {
  const s = useDashboard();

  return (
    <>
      <div className="section-head">
        <div className="hstack" style={{ justifyContent: "space-between" }}>
          <div>
            <div className="section-title">Activity</div>
            <div className="section-desc">Control commands the worker drains from the queue.</div>
          </div>
          <Button variant="secondary" disabled={s.cmd.busy} onClick={() => s.pollCi()}>
            Sweep CI now
          </Button>
        </div>
      </div>
      <div className="section-body">
        {s.commands.length === 0 ? (
          <div className="empty">No commands yet.</div>
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Type</th>
                  <th>Repository</th>
                  <th>Agent</th>
                  <th>Status</th>
                  <th>Result / Error</th>
                </tr>
              </thead>
              <tbody>
                {s.commands.map((c) => (
                  <tr key={c.id}>
                    <td className="faint nowrap">{fmtFull(c.created_at)}</td>
                    <td className="mono">{c.type}</td>
                    <td className="mono">{c.project_id || "—"}</td>
                    <td className="mono">{c.agent_name || "—"}</td>
                    <td>
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="mono faint" style={{ fontSize: "var(--text-xs)" }}>
                      {c.error || (c.result ? JSON.stringify(c.result) : "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
