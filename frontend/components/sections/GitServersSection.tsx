/* Git Servers — one entry per forge host, carrying the server's own credentials:
 * a forge token (stored encrypted, write-only) and an SSH deploy key whose public half
 * is shown here to paste into the forge. Projects on a configured server need no
 * per-repo credentials. */
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

const empty = {
  hostname: "",
  forge_type: "github",
  token_env_var: "",
  base_url: "",
  token: "",
  generate_ssh_key: true,
};

function PublicKey({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable (http) — the key is selectable below */
    }
  };
  return (
    <div style={{ marginTop: 10 }}>
      <div className="hstack" style={{ justifyContent: "space-between" }}>
        <span className="eyebrow">SSH public key — add it to the forge (deploy key)</span>
        <Button size="sm" variant="secondary" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre
        className="mono"
        style={{
          fontSize: "var(--text-xs)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
          margin: "6px 0 0",
          padding: 8,
          border: "1px solid var(--border-default)",
          borderRadius: 6,
          userSelect: "all",
        }}
      >
        {value}
      </pre>
    </div>
  );
}

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
      token: "",
      generate_ssh_key: false,
    });
    setEditing(true);
  };

  return (
    <>
      <div className="section-head">
        <div className="section-title">Git Servers</div>
        <div className="section-desc">
          Each server carries its own credentials: a forge token (encrypted at rest, used by
          agents&apos; <span className="mono">forge</span> + git) and an SSH deploy key — paste
          the public key into the forge. New repositories are added by picking a server and
          typing owner/name.
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
              placeholder="github.com"
              disabled={editing}
            />
            <Select
              label="Type"
              value={form.forge_type}
              onChange={(v) => setForm({ ...form, forge_type: v })}
              options={FORGE_OPTS}
            />
            <Input
              label={editing ? "Forge token (blank = keep current)" : "Forge token"}
              type="password"
              value={form.token}
              onChange={(v) => setForm({ ...form, token: v })}
              placeholder="stored encrypted; used by forge + git"
            />
            <Input
              label="Base URL (optional)"
              value={form.base_url}
              onChange={(v) => setForm({ ...form, base_url: v })}
              placeholder="https://git.corp.internal:8443"
            />
            <Input
              label="Token env var override (optional)"
              value={form.token_env_var}
              onChange={(v) => setForm({ ...form, token_env_var: v })}
              placeholder="GITEA_TOKEN"
            />
            <label className="field">
              <span className="field-label">SSH deploy key</span>
              <label className="hstack" style={{ gap: 8, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={form.generate_ssh_key}
                  onChange={(e) => setForm({ ...form, generate_ssh_key: e.target.checked })}
                />
                <span style={{ fontSize: "var(--text-sm)" }}>
                  {editing ? "Regenerate keypair (replaces the current key)" : "Generate a keypair"}
                </span>
              </label>
            </label>
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
                <Badge tone={h.has_token ? "success" : "neutral"}>
                  {h.has_token ? "token stored" : "no token"}
                </Badge>
                <Badge tone={h.ssh_public_key ? "success" : "neutral"}>
                  {h.ssh_public_key ? "ssh key" : "no ssh key"}
                </Badge>
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
            {h.ssh_public_key && <PublicKey value={h.ssh_public_key} />}
          </Card>
        ))}
      </div>
    </>
  );
}
