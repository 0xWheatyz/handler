/* Repositories — register / edit / remove the projects (repos) Handler manages.
 * Maps the design's "Repositories" pane to Handler's project registry. */
"use client";

import { useMemo, useState } from "react";
import { useDashboard } from "@/components/store";
import { Badge, Button, Card, Input } from "@/components/ui";
import { fmtFull } from "@/lib/format";
import type { Project } from "@/lib/api";

const CRED_HELP = "credential_ref is a pointer, never the token (env: / file: / db:). cmd: is CLI-only.";

const empty = { id: "", root_dir: "", git_remote: "", credential_ref: "" };

export function RepositoriesSection() {
  const s = useDashboard();
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(false);

  const agentCount = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of s.agents) m.set(a.project_id, (m.get(a.project_id) ?? 0) + 1);
    return m;
  }, [s.agents]);

  const reset = () => {
    setForm(empty);
    setEditing(false);
  };

  const save = async () => {
    const ok = editing
      ? await s.updateProject(form.id, form)
      : await s.createProject(form);
    if (ok) reset();
  };

  const edit = (p: Project) => {
    setForm({
      id: p.id,
      root_dir: p.root_dir,
      git_remote: p.git_remote ?? "",
      credential_ref: p.credential_ref ?? "",
    });
    setEditing(true);
  };

  return (
    <>
      <div className="section-head">
        <div className="section-title">Repositories</div>
        <div className="section-desc">
          Repos Handler manages. Each carries its own agents, history, and credentials.
        </div>
      </div>
      <div className="section-body">
        <Card>
          <div className="card-head" style={{ marginBottom: 14 }}>
            <span className="card-title" style={{ fontSize: "var(--text-md)", color: "var(--text-heading)" }}>
              {editing ? `Edit repository · ${form.id}` : "Register a repository"}
            </span>
          </div>
          <div className="form-grid">
            <Input
              label="ID / slug"
              value={form.id}
              onChange={(v) => setForm({ ...form, id: v })}
              placeholder="leeworks-api"
              disabled={editing}
            />
            <Input
              label="Root dir"
              value={form.root_dir}
              onChange={(v) => setForm({ ...form, root_dir: v })}
              placeholder="/var/lib/handler/projects/leeworks"
            />
            <Input
              label="Git remote"
              value={form.git_remote}
              onChange={(v) => setForm({ ...form, git_remote: v })}
              placeholder="git@github.com:user/repo.git (optional)"
            />
            <Input
              label="Credential ref"
              value={form.credential_ref}
              onChange={(v) => setForm({ ...form, credential_ref: v })}
              placeholder="env:VAR / file:/path / db:id"
            />
          </div>
          <p className="faint" style={{ fontSize: "var(--text-xs)", margin: "10px 0 0" }}>
            {CRED_HELP}
          </p>
          <div className="hstack mt14">
            <Button
              variant="primary"
              disabled={s.cmd.busy || !form.id.trim() || !form.root_dir.trim()}
              onClick={save}
            >
              {editing ? "Save changes" : "Register"}
            </Button>
            {editing && (
              <Button variant="ghost" onClick={reset}>
                Cancel
              </Button>
            )}
          </div>
        </Card>

        {s.projects.length === 0 && <div className="empty">No repositories registered.</div>}

        {s.projects.map((p) => (
          <Card key={p.id}>
            <div className="card-head">
              <span className="card-title">{p.id}</span>
              <Badge tone="info" pill>
                {agentCount.get(p.id) ?? 0} {(agentCount.get(p.id) ?? 0) === 1 ? "agent" : "agents"}
              </Badge>
            </div>
            <div className="mono faint" style={{ fontSize: "var(--text-xs)", marginTop: 4 }}>
              {p.root_dir}
              {p.git_remote ? ` · ${p.git_remote}` : ""}
            </div>
            <div className="hstack" style={{ marginTop: 12, justifyContent: "space-between" }}>
              <span className="faint mono" style={{ fontSize: "var(--text-xs)" }}>
                cred {p.credential_ref || "—"} · added {fmtFull(p.created_at)}
              </span>
              <div className="hstack">
                <Button size="sm" variant="secondary" onClick={() => edit(p)}>
                  Edit
                </Button>
                <Button size="sm" variant="danger" onClick={() => s.deleteProject(p.id)}>
                  Remove
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
