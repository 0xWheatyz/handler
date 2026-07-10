/* Approvals — record a per-branch verdict (the review gate). A verdict is enqueued as a
 * control command so the worker can read the reviewed HEAD and pin the approval. */
"use client";

import { useMemo, useState } from "react";
import { useDashboard } from "@/components/store";
import { Badge, Button, Card, Input, Select, StatusBadge } from "@/components/ui";
import { fmtFull, shortSha } from "@/lib/format";

const STATUS_OPTS = [
  { value: "approved", label: "approve" },
  { value: "rejected", label: "reject" },
];

const empty = { branch: "", status: "approved", agent_name: "", sha: "", note: "" };

export function ApprovalsSection() {
  const s = useDashboard();
  const [form, setForm] = useState(empty);

  const projectOpts = useMemo(
    () => s.projects.map((p) => ({ value: p.id, label: p.id })),
    [s.projects],
  );

  const submit = async () => {
    await s.submitApproval(form);
    setForm(empty);
  };

  return (
    <>
      <div className="section-head">
        <div className="section-title">Approvals</div>
        <div className="section-desc">
          A merge is denied unless a standing approval exists — made by a different agent, pinned to
          the reviewed commit.
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
                  Record a verdict
                </span>
              </div>
              <div className="form-grid">
                <Input label="Branch" value={form.branch} onChange={(v) => setForm({ ...form, branch: v })} placeholder="feat/auth" />
                <Select label="Verdict" value={form.status} onChange={(v) => setForm({ ...form, status: v })} options={STATUS_OPTS} />
                <Input label="Agent" value={form.agent_name} onChange={(v) => setForm({ ...form, agent_name: v })} placeholder="reads its HEAD (optional)" />
                <Input label="SHA" value={form.sha} onChange={(v) => setForm({ ...form, sha: v })} placeholder="pins the approval (optional)" />
              </div>
              <div className="mt14">
                <Input label="Note" value={form.note} onChange={(v) => setForm({ ...form, note: v })} placeholder="optional" />
              </div>
              <div className="hstack mt14">
                <Button variant="primary" disabled={s.cmd.busy || !form.branch.trim()} onClick={submit}>
                  Enqueue verdict
                </Button>
              </div>
            </Card>

            {s.approvals.length === 0 ? (
              <div className="empty">No approvals recorded.</div>
            ) : (
              <div className="table-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Branch</th>
                      <th>Verdict</th>
                      <th>By</th>
                      <th>SHA</th>
                      <th>Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.approvals.map((ap) => (
                      <tr key={ap.id}>
                        <td className="faint nowrap">{fmtFull(ap.created_at)}</td>
                        <td className="mono">{ap.branch}</td>
                        <td>
                          <StatusBadge status={ap.status} />
                        </td>
                        <td>{ap.approved_by_agent_id ? `agent ${ap.approved_by_agent_id}` : ap.actor || "—"}</td>
                        <td className="mono">{shortSha(ap.approved_sha)}</td>
                        <td>{ap.note || "—"}</td>
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
