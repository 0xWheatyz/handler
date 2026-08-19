/* Agents — spawn a new agent into a repository and manage the ones already running.
 * Spawning enqueues a control command that the worker turns into a tmux + claude process. */
"use client";

import { Fragment, useMemo, useState } from "react";
import { useDashboard } from "@/components/store";
import { Badge, Button, Card, Input, Select, StatusBadge, Textarea } from "@/components/ui";
import { fmtFull, timeAgo } from "@/lib/format";

const ROLE_OPTS = [
  { value: "", label: "Role — none" },
  { value: "scout", label: "scout" },
  { value: "planner", label: "planner" },
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
  model_id: "",
};

export function AgentsSection() {
  const s = useDashboard();
  const [form, setForm] = useState(emptySpawn);

  const projectOpts = useMemo(
    () => s.projects.map((p) => ({ value: p.id, label: p.id })),
    [s.projects],
  );
  /* The seamless switch: Claude subscription by default, plus every enabled backend
   * registered on the Claude page's Models tab. Same binary, hooks, and skills either
   * way — only the ANTHROPIC_* env of the launched process differs. */
  const modelOpts = useMemo(
    () => [
      { value: "", label: "Claude (subscription)" },
      ...s.claudeModels
        .filter((m) => m.enabled)
        .map((m) => ({ value: String(m.id), label: `${m.name} (${m.model})` })),
    ],
    [s.claudeModels],
  );
  const modelName = useMemo(() => {
    const byId = new Map(s.claudeModels.map((m) => [m.id, m.name]));
    return (id: number | null | undefined) => (id == null ? null : byId.get(id) ?? `#${id}`);
  }, [s.claudeModels]);
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
                <Select
                  label="Model"
                  value={form.model_id}
                  onChange={(v) => setForm({ ...form, model_id: v })}
                  options={modelOpts}
                />
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
                      <th>Model</th>
                      <th>Status</th>
                      <th>Working dir</th>
                      <th>Created</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((a) => (
                      <Fragment key={a.id}>
                        <tr>
                          <td className="mono">{a.name}</td>
                          <td>{a.role ? <Badge tone="info">{a.role}</Badge> : "—"}</td>
                          <td>
                            {a.model_id != null ? (
                              <Badge tone="warning">{modelName(a.model_id)}</Badge>
                            ) : (
                              <Badge tone="neutral">claude</Badge>
                            )}
                          </td>
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
                        {(a.status === "working" || a.status === "crashed") && a.last_output?.trim() && (
                          <tr>
                            <td colSpan={7} style={{ paddingTop: 0 }}>
                              <div className="faint" style={{ fontSize: "var(--text-xs)", marginBottom: 4 }}>
                                {a.status === "crashed" ? "last output before crash" : "live output"}
                                {a.output_at ? ` · ${timeAgo(a.output_at)}` : ""}
                              </div>
                              <pre
                                className="mono"
                                style={{
                                  margin: 0,
                                  padding: "8px 10px",
                                  background: "var(--surface-2, rgba(0,0,0,0.25))",
                                  borderRadius: 6,
                                  fontSize: "var(--text-xs)",
                                  lineHeight: 1.4,
                                  maxHeight: 220,
                                  overflow: "auto",
                                  whiteSpace: "pre",
                                }}
                              >
                                {a.last_output}
                              </pre>
                            </td>
                          </tr>
                        )}
                      </Fragment>
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
