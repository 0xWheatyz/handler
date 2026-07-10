/* Schedules — recurring agent spawns. Every interval the worker starts a fresh,
 * stateless agent named <prefix>-<timestamp> with the stored prompt. The canonical
 * pattern: keep state in a file in the repo and have the prompt continue from it. */
"use client";

import { useMemo, useState } from "react";
import { useDashboard } from "@/components/store";
import { Badge, Button, Card, Input, Select, Textarea, Toggle } from "@/components/ui";
import { fmtFull } from "@/lib/format";

const ROLE_OPTS = [
  { value: "", label: "Role — none" },
  { value: "junior", label: "junior" },
  { value: "senior", label: "senior" },
  { value: "deploy", label: "deploy" },
];

const INTERVAL_OPTS = [
  { value: "900", label: "every 15 minutes" },
  { value: "1800", label: "every 30 minutes" },
  { value: "3600", label: "every hour" },
  { value: "21600", label: "every 6 hours" },
  { value: "86400", label: "every day" },
  { value: "604800", label: "every week" },
];

const TASK_PLACEHOLDER =
  "Read @notes.md and continue from where it left off. Before finishing, overwrite " +
  "@notes.md with the current state so the next run can pick up from there.";

function intervalLabel(seconds: number): string {
  const opt = INTERVAL_OPTS.find((o) => Number(o.value) === seconds);
  if (opt) return opt.label;
  if (seconds % 3600 === 0) return `every ${seconds / 3600}h`;
  if (seconds % 60 === 0) return `every ${seconds / 60}m`;
  return `every ${seconds}s`;
}

const emptyForm = { name_prefix: "", task: "", interval: "3600", role: "" };

export function SchedulesSection() {
  const s = useDashboard();
  const [form, setForm] = useState(emptyForm);

  const projectOpts = useMemo(
    () => s.projects.map((p) => ({ value: p.id, label: p.id })),
    [s.projects],
  );

  const create = async () => {
    const ok = await s.createSchedule(s.selectedProjectId, {
      name_prefix: form.name_prefix,
      task: form.task,
      interval_seconds: Number(form.interval),
      role: form.role,
    });
    if (ok) setForm(emptyForm);
  };

  return (
    <>
      <div className="section-head">
        <div className="section-title">Schedules</div>
        <div className="section-desc">
          Spawn a fresh agent on an interval. Each run is stateless — keep continuity in a
          file the prompt reads and overwrites.
        </div>
      </div>
      <div className="section-body">
        {s.projects.length === 0 ? (
          <div className="empty">Register a repository first.</div>
        ) : (
          <>
            <div className="row">
              <div style={{ width: 260 }}>
                <Select
                  label="Repository"
                  value={s.selectedProjectId}
                  onChange={s.selectProject}
                  options={projectOpts}
                />
              </div>
            </div>

            <Card>
              <div className="card-head" style={{ marginBottom: 14 }}>
                <span className="card-title" style={{ fontSize: "var(--text-md)", color: "var(--text-heading)" }}>
                  New schedule
                </span>
              </div>
              <div className="form-grid">
                <Input
                  label="Name prefix"
                  value={form.name_prefix}
                  onChange={(v) => setForm({ ...form, name_prefix: v })}
                  placeholder="nightly"
                />
                <Select
                  label="Interval"
                  value={form.interval}
                  onChange={(v) => setForm({ ...form, interval: v })}
                  options={INTERVAL_OPTS}
                />
                <Select
                  label="Role"
                  value={form.role}
                  onChange={(v) => setForm({ ...form, role: v })}
                  options={ROLE_OPTS}
                />
              </div>
              <div className="mt14">
                <Textarea
                  label="Prompt (the task every run starts with)"
                  value={form.task}
                  onChange={(v) => setForm({ ...form, task: v })}
                  rows={3}
                  placeholder={TASK_PLACEHOLDER}
                />
              </div>
              <p className="faint" style={{ fontSize: "var(--text-xs)", margin: "10px 0 0" }}>
                Runs are named <span className="mono">{form.name_prefix.trim() || "prefix"}-YYYYMMDD-HHMMSS</span>.
                The repo is pulled before every run; the first run fires on the worker&apos;s next
                pass.
              </p>
              <div className="hstack mt14">
                <Button
                  variant="primary"
                  disabled={s.cmd.busy || !form.name_prefix.trim() || !form.task.trim()}
                  onClick={create}
                >
                  Create schedule
                </Button>
              </div>
            </Card>

            {s.schedules.length === 0 ? (
              <div className="empty">No schedules yet.</div>
            ) : (
              <div className="table-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>On</th>
                      <th>Name</th>
                      <th>Repository</th>
                      <th>Interval</th>
                      <th>Prompt</th>
                      <th>Next run</th>
                      <th>Last run</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {s.schedules.map((sc) => (
                      <tr key={sc.id}>
                        <td>
                          <Toggle
                            on={sc.enabled}
                            onClick={() => s.updateSchedule(sc.id, { enabled: !sc.enabled })}
                          />
                        </td>
                        <td className="mono">
                          {sc.name_prefix}
                          {sc.role ? (
                            <>
                              {" "}
                              <Badge tone="info">{sc.role}</Badge>
                            </>
                          ) : null}
                        </td>
                        <td className="mono faint">{sc.project_id}</td>
                        <td className="nowrap">{intervalLabel(sc.interval_seconds)}</td>
                        <td className="faint" style={{ maxWidth: 340 }}>
                          <span className="truncate" style={{ display: "block" }} title={sc.task}>
                            {sc.task}
                          </span>
                        </td>
                        <td className="faint nowrap">{sc.enabled ? fmtFull(sc.next_run_at) : "paused"}</td>
                        <td className="faint nowrap">{fmtFull(sc.last_run_at)}</td>
                        <td className="nowrap">
                          <Button size="sm" variant="danger" onClick={() => s.deleteSchedule(sc.id)}>
                            Delete
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
