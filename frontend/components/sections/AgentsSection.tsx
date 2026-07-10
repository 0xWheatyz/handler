/* Agents — spawn a new agent into a repository and manage the ones already running.
 * Spawning enqueues a control command that the worker turns into a tmux + claude process. */
"use client";

import { useMemo, useState } from "react";
import { useDashboard } from "@/components/store";
import { Badge, Button, Card, Input, Select, StatusBadge, Textarea } from "@/components/ui";
import { fmtFull } from "@/lib/format";

const ROLE_OPTS = [
  { value: "", label: "Role — none" },
  { value: "junior", label: "junior" },
  { value: "senior", label: "senior" },
  { value: "deploy", label: "deploy" },
];
const PLACEMENT_OPTS = [
  { value: "worktree", label: "git worktree on branch" },
  { value: "subdir", label: "subdir under root" },
];

const emptySpawn = {
  name: "",
  role: "",
  placement: "worktree" as "worktree" | "subdir",
  worktree: "",
  subdir: "",
  task: "",
};

export function AgentsSection() {
  const s = useDashboard();
  const [form, setForm] = useState(emptySpawn);

  const projectOpts = useMemo(
    () => s.projects.map((p) => ({ value: p.id, label: p.id })),
    [s.projects],
  );
  const agents = useMemo(
    () => s.agents.filter((a) => a.project_id === s.selectedProjectId),
    [s.agents, s.selectedProjectId],
  );

  const spawn = async () => {
    const ok = await s.spawnAgent(form);
    if (ok) setForm(emptySpawn);
  };

  return (
    <>
      <div className="section-head">
        <div className="section-title">Agents</div>
        <div className="section-desc">Spawn agents into a repository and manage running sessions.</div>
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
                  Spawn an agent
                </span>
              </div>
              <div className="form-grid">
                <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} placeholder="junior" />
                <Select label="Role" value={form.role} onChange={(v) => setForm({ ...form, role: v })} options={ROLE_OPTS} />
                <Select
                  label="Placement"
                  value={form.placement}
                  onChange={(v) => setForm({ ...form, placement: v as "worktree" | "subdir" })}
                  options={PLACEMENT_OPTS}
                />
                {form.placement === "worktree" ? (
                  <Input label="Branch" value={form.worktree} onChange={(v) => setForm({ ...form, worktree: v })} placeholder="feat/auth" />
                ) : (
                  <Input label="Subdir" value={form.subdir} onChange={(v) => setForm({ ...form, subdir: v })} placeholder="api" />
                )}
              </div>
              <div className="mt14">
                <Textarea
                  label="Initial task"
                  value={form.task}
                  onChange={(v) => setForm({ ...form, task: v })}
                  rows={2}
                  placeholder="initial task / prompt (optional)"
                />
              </div>
              <div className="hstack mt14">
                <Button variant="primary" disabled={s.cmd.busy || !form.name.trim()} onClick={spawn}>
                  Spawn
                </Button>
              </div>
            </Card>

            {agents.length === 0 ? (
              <div className="empty">No agents in this repository.</div>
            ) : (
              <div className="table-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Working dir</th>
                      <th>Created</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((a) => (
                      <tr key={a.id}>
                        <td className="mono">{a.name}</td>
                        <td>{a.role ? <Badge tone="info">{a.role}</Badge> : "—"}</td>
                        <td>
                          <StatusBadge status={a.status} />
                        </td>
                        <td className="mono faint">{a.working_dir}</td>
                        <td className="faint nowrap">{fmtFull(a.created_at)}</td>
                        <td className="nowrap">
                          <div className="hstack">
                            <Button size="sm" variant="ghost" onClick={() => s.selectRun(a.project_id, a.name)}>
                              Open
                            </Button>
                            <Button size="sm" variant="secondary" onClick={() => s.killAgent(a.project_id, a.name)}>
                              Kill
                            </Button>
                            <Button size="sm" variant="danger" onClick={() => s.deleteAgent(a.project_id, a.name)}>
                              Delete
                            </Button>
                          </div>
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
