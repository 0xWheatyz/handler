/* Git Servers — the forge host registry. Each row maps a host to the token env var to
 * inject at spawn (and the credential-helper scope). Holds no secrets, only the var name. */
"use client";

import { useState } from "react";
import { useDashboard } from "@/components/store";
import { Badge, Button, Card, Input, Select } from "@/components/ui";
import type { Host } from "@/lib/api";

const FORGE_OPTS = [
  { value: "github", label: "github" },
  { value: "gitlab", label: "gitlab" },
  { value: "gitea", label: "gitea" },
  { value: "forgejo", label: "forgejo" },
  { value: "bitbucket", label: "bitbucket" },
];

const empty = { hostname: "", forge_type: "github", token_env_var: "", base_url: "" };

export function GitServersSection() {
  const s = useDashboard();
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(false);

  const reset = () => {
    setForm(empty);
    setEditing(false);
  };

  const save = async () => {
    const ok = editing ? await s.updateHost(form.hostname, form) : await s.createHost(form);
    if (ok) reset();
  };

  const edit = (h: Host) => {
    setForm({
      hostname: h.hostname,
      forge_type: h.forge_type,
      token_env_var: h.token_env_var ?? "",
      base_url: h.base_url ?? "",
    });
    setEditing(true);
  };

  return (
    <>
      <div className="section-head">
        <div className="section-title">Git Servers</div>
        <div className="section-desc">
          Maps a git host to the token env var injected at spawn. The built-in host map is the
          fallback when no row matches.
        </div>
      </div>
      <div className="section-body">
        <Card>
          <div className="card-head" style={{ marginBottom: 14 }}>
            <span className="card-title" style={{ fontSize: "var(--text-md)", color: "var(--text-heading)" }}>
              {editing ? `Edit server · ${form.hostname}` : "Add a git server"}
            </span>
          </div>
          <div className="form-grid">
            <Input
              label="Hostname"
              value={form.hostname}
              onChange={(v) => setForm({ ...form, hostname: v })}
              placeholder="git.corp.internal"
              disabled={editing}
            />
            <Select
              label="Type"
              value={form.forge_type}
              onChange={(v) => setForm({ ...form, forge_type: v })}
              options={FORGE_OPTS}
            />
            <Input
              label="Token env var"
              value={form.token_env_var}
              onChange={(v) => setForm({ ...form, token_env_var: v })}
              placeholder="GITEA_TOKEN"
            />
            <Input
              label="Base URL"
              value={form.base_url}
              onChange={(v) => setForm({ ...form, base_url: v })}
              placeholder="https://git.corp.internal (optional)"
            />
          </div>
          <div className="hstack mt14">
            <Button variant="primary" disabled={s.cmd.busy || !form.hostname.trim()} onClick={save}>
              {editing ? "Save changes" : "Add server"}
            </Button>
            {editing && (
              <Button variant="ghost" onClick={reset}>
                Cancel
              </Button>
            )}
          </div>
        </Card>

        {s.hosts.length === 0 && (
          <div className="empty">No git servers registered (built-in host map still applies).</div>
        )}

        {s.hosts.map((h) => (
          <Card key={h.hostname}>
            <div className="card-head">
              <span className="mono" style={{ fontWeight: "var(--fw-bold)", fontSize: "var(--text-lg)", color: "var(--text-heading)" }}>
                {h.hostname}
              </span>
              <div className="hstack">
                <Badge tone="info">{h.forge_type}</Badge>
                <Button size="sm" variant="secondary" onClick={() => edit(h)}>
                  Edit
                </Button>
                <Button size="sm" variant="danger" onClick={() => s.deleteHost(h.hostname)}>
                  Remove
                </Button>
              </div>
            </div>
            <div className="mono faint" style={{ fontSize: "var(--text-xs)", marginTop: 8 }}>
              token env {h.token_env_var || "—"}
              {h.base_url ? ` · ${h.base_url}` : ""}
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
