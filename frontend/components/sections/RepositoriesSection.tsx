/* Repositories — the projects Handler manages. Adding one is now server-first: pick a
 * configured git server, type owner/name, and Handler derives the remote, decides where
 * the clone lives, and pulls it (stateless workflows don't care about disk paths).
 * Manual mode (an existing checkout) remains for everything else. */
"use client";

import { useMemo, useState } from "react";
import { useDashboard, type NewProjectBody } from "@/components/store";
import { Badge, Button, Card, Input, Select, Tabs } from "@/components/ui";
import { fmtFull } from "@/lib/format";
import type { Project } from "@/lib/api";

const CRED_HELP =
  "Optional override — projects on a configured git server use its stored token automatically. " +
  "credential_ref is a pointer, never the token (env: / file: / db:host:<hostname>).";

const empty: NewProjectBody = {
  mode: "server",
  git_server: "",
  repo: "",
  id: "",
  root_dir: "",
  git_remote: "",
  credential_ref: "",
};

export function RepositoriesSection() {
  const s = useDashboard();
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(false);

  const agentCount = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of s.agents) m.set(a.project_id, (m.get(a.project_id) ?? 0) + 1);
    return m;
  }, [s.agents]);

  const serverOpts = useMemo(
    () => [
      { value: "", label: s.hosts.length ? "Pick a git server…" : "No git servers configured" },
      ...s.hosts.map((h) => ({ value: h.hostname, label: `${h.hostname} (${h.forge_type})` })),
    ],
    [s.hosts],
  );

  const reset = () => {
    setForm(empty);
    setEditing(false);
  };

  const save = async () => {
    const ok = editing ? await s.updateProject(form.id, form) : await s.createProject(form);
    if (ok) reset();
  };

  const edit = (p: Project) => {
    setForm({
      ...empty,
      mode: "manual",
      id: p.id,
      root_dir: p.root_dir,
      git_remote: p.git_remote ?? "",
      credential_ref: p.credential_ref ?? "",
    });
    setEditing(true);
  };

  const canSave = editing
    ? !!form.root_dir.trim()
    : form.mode === "server"
      ? !!form.git_server && /^[\w.-]+\/[\w.-]+$/.test(form.repo.trim())
      : !!form.id.trim() && !!form.root_dir.trim();

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
              {editing ? `Edit repository · ${form.id}` : "Add a repository"}
            </span>
          </div>

          {!editing && (
            <div style={{ marginBottom: 14 }}>
              <Tabs
                tabs={[
                  { value: "server", label: "From a git server" },
                  { value: "manual", label: "Manual (existing checkout)" },
                ]}
                value={form.mode}
                onChange={(v) => setForm({ ...form, mode: v as "server" | "manual" })}
              />
            </div>
          )}

          {!editing && form.mode === "server" ? (
            <>
              <div className="form-grid">
                <Select
                  label="Git server"
                  value={form.git_server}
                  onChange={(v) => setForm({ ...form, git_server: v })}
                  options={serverOpts}
                />
                <Input
                  label="Repository (owner/name)"
                  value={form.repo}
                  onChange={(v) => setForm({ ...form, repo: v })}
                  placeholder="me/coolproj"
                />
                <Input
                  label="ID / slug (optional — defaults to the repo name)"
                  value={form.id}
                  onChange={(v) => setForm({ ...form, id: v })}
                  placeholder="coolproj"
                />
              </div>
              <p className="faint" style={{ fontSize: "var(--text-xs)", margin: "10px 0 0" }}>
                The repo is always pulled: Handler derives the remote from the server (ssh when it
                has a deploy key, https via the stored token otherwise), clones it under
                PROJECTS_ROOT, and keeps it fresh before every run.
              </p>
            </>
          ) : (
            <>
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
                  placeholder="env:VAR / file:/path / db:host:github.com"
                />
              </div>
              <p className="faint" style={{ fontSize: "var(--text-xs)", margin: "10px 0 0" }}>
                {CRED_HELP}
              </p>
            </>
          )}

          <div className="hstack mt14">
            <Button variant="primary" disabled={s.cmd.busy || !canSave} onClick={save}>
              {editing ? "Save changes" : form.mode === "server" ? "Add & pull" : "Register"}
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
                cred {p.credential_ref || "server default"} · added {fmtFull(p.created_at)}
              </span>
              <div className="hstack">
                {p.git_remote && (
                  <Button size="sm" variant="secondary" onClick={() => s.syncProject(p.id)}>
                    Pull now
                  </Button>
                )}
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
