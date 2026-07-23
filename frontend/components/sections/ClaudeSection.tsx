/* Claude — the management page for the Claude Code install agents run on: the account
 * login (moved here from the old Claude Login page), plus the operator-managed skills,
 * MCP connectors, plugins, and permission overrides. Everything except the login is a
 * plain DB write that the control container applies at the NEXT launch of every agent —
 * skills sync to the workers' user-level ~/.claude/skills, connectors become each run's
 * --mcp-config file, and plugins/permissions fold into the generated settings.json. */
"use client";

import { useState } from "react";
import { useDashboard } from "@/components/store";
import type { ConnectorBody, PluginBody, SkillBody } from "@/components/store";
import { Badge, Button, Card, Input, Select, Tabs, Textarea, Toggle } from "@/components/ui";
import type { ClaudeConnector, ClaudePlugin, ClaudeSkill } from "@/lib/api";
import { ClaudeLoginPanel } from "@/components/sections/LoginSection";

/* KEY=VALUE-per-line <-> map helpers for connector env/headers. */
function parseKeyValues(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    out[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim();
  }
  return out;
}

function formatKeyValues(map: Record<string, string> | null | undefined): string {
  return Object.entries(map ?? {})
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");
}

function parseLines(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

/* ---- Skills ------------------------------------------------------------------------ */

const emptySkill = { name: "", description: "", content: "", enabled: true };

function SkillsPanel() {
  const s = useDashboard();
  const [form, setForm] = useState(emptySkill);
  const [editingId, setEditingId] = useState<number | null>(null);

  const reset = () => {
    setForm(emptySkill);
    setEditingId(null);
  };

  const save = async () => {
    const body: SkillBody = { ...form };
    const ok =
      editingId != null
        ? await s.updateClaudeSkill(editingId, body)
        : await s.createClaudeSkill(body);
    if (ok) reset();
  };

  const edit = (sk: ClaudeSkill) => {
    setForm({
      name: sk.name,
      description: sk.description ?? "",
      content: sk.content,
      enabled: sk.enabled,
    });
    setEditingId(sk.id);
  };

  return (
    <>
      <div className="faint" style={{ fontSize: "var(--text-sm)", marginBottom: 14 }}>
        Custom Claude Code skills, synced to every worker&apos;s{" "}
        <span className="mono">~/.claude/skills</span> at each launch. The description is
        what makes Claude pick the skill up — say when to use it.
      </div>
      <Card>
        <div className="card-head" style={{ marginBottom: 14 }}>
          <span className="card-title" style={{ fontSize: "var(--text-md)", color: "var(--text-heading)" }}>
            {editingId != null ? `Edit skill · ${form.name}` : "Add a skill"}
          </span>
        </div>
        <div className="form-grid">
          <Input
            label="Name (slug — becomes the skill directory)"
            value={form.name}
            onChange={(v) => setForm({ ...form, name: v })}
            placeholder="deploy-checklist"
          />
          <Input
            label="Description (when should Claude use it?)"
            value={form.description}
            onChange={(v) => setForm({ ...form, description: v })}
            placeholder="Use when preparing or reviewing a deploy."
          />
        </div>
        <div style={{ marginTop: 10 }}>
          <Textarea
            label="SKILL.md body (markdown)"
            value={form.content}
            onChange={(v) => setForm({ ...form, content: v })}
            rows={8}
            placeholder={"# Deploy checklist\n\n1. ..."}
          />
        </div>
        <div className="hstack mt14">
          <Button
            variant="primary"
            disabled={!form.name.trim() || !form.content.trim()}
            onClick={save}
          >
            {editingId != null ? "Save changes" : "Add skill"}
          </Button>
          {editingId != null && (
            <Button variant="ghost" onClick={reset}>
              Cancel
            </Button>
          )}
        </div>
      </Card>

      {s.claudeSkills.length === 0 && <div className="empty">No custom skills yet.</div>}

      {s.claudeSkills.map((sk) => (
        <Card key={sk.id}>
          <div className="card-head">
            <span className="mono" style={{ fontWeight: "var(--fw-bold)", fontSize: "var(--text-lg)", color: "var(--text-heading)" }}>
              {sk.name}
            </span>
            <div className="hstack">
              <Badge tone={sk.enabled ? "success" : "neutral"}>
                {sk.enabled ? "enabled" : "disabled"}
              </Badge>
              <Toggle on={sk.enabled} onClick={() => s.updateClaudeSkill(sk.id, { enabled: !sk.enabled })} />
              <Button size="sm" variant="secondary" onClick={() => edit(sk)}>
                Edit
              </Button>
              <Button size="sm" variant="danger" onClick={() => s.deleteClaudeSkill(sk.id)}>
                Remove
              </Button>
            </div>
          </div>
          {sk.description && (
            <div className="faint" style={{ fontSize: "var(--text-sm)", marginTop: 8 }}>
              {sk.description}
            </div>
          )}
        </Card>
      ))}
    </>
  );
}

/* ---- Connectors (MCP servers) ------------------------------------------------------ */

const TRANSPORT_OPTS = [
  { value: "stdio", label: "stdio (run a command)" },
  { value: "http", label: "http (remote server)" },
  { value: "sse", label: "sse (remote server, legacy)" },
];

const emptyConnector = {
  name: "",
  transport: "stdio" as ConnectorBody["transport"],
  command: "",
  args: "",
  env: "",
  url: "",
  headers: "",
  enabled: true,
};

function ConnectorsPanel() {
  const s = useDashboard();
  const [form, setForm] = useState(emptyConnector);
  const [editingId, setEditingId] = useState<number | null>(null);

  const reset = () => {
    setForm(emptyConnector);
    setEditingId(null);
  };

  const save = async () => {
    const body: ConnectorBody = {
      name: form.name,
      transport: form.transport,
      command: form.command.trim() || null,
      args: parseLines(form.args),
      env: parseKeyValues(form.env),
      url: form.url.trim() || null,
      headers: parseKeyValues(form.headers),
      enabled: form.enabled,
    };
    const ok =
      editingId != null
        ? await s.updateClaudeConnector(editingId, body)
        : await s.createClaudeConnector(body);
    if (ok) reset();
  };

  const edit = (c: ClaudeConnector) => {
    setForm({
      name: c.name,
      transport: c.transport,
      command: c.command ?? "",
      args: (c.args ?? []).join("\n"),
      env: formatKeyValues(c.env),
      url: c.url ?? "",
      headers: formatKeyValues(c.headers),
      enabled: c.enabled,
    });
    setEditingId(c.id);
  };

  const stdio = form.transport === "stdio";

  return (
    <>
      <div className="faint" style={{ fontSize: "var(--text-sm)", marginBottom: 14 }}>
        MCP servers agents can reach. Passed to each run as its{" "}
        <span className="mono">--mcp-config</span> file, so nothing lands in the
        repository tree. stdio commands run inside the control container.
      </div>
      <Card>
        <div className="card-head" style={{ marginBottom: 14 }}>
          <span className="card-title" style={{ fontSize: "var(--text-md)", color: "var(--text-heading)" }}>
            {editingId != null ? `Edit connector · ${form.name}` : "Add a connector"}
          </span>
        </div>
        <div className="form-grid">
          <Input
            label="Name"
            value={form.name}
            onChange={(v) => setForm({ ...form, name: v })}
            placeholder="github"
          />
          <Select
            label="Transport"
            value={form.transport}
            onChange={(v) => setForm({ ...form, transport: v as ConnectorBody["transport"] })}
            options={TRANSPORT_OPTS}
          />
          {stdio ? (
            <>
              <Input
                label="Command"
                value={form.command}
                onChange={(v) => setForm({ ...form, command: v })}
                placeholder="npx"
              />
              <Textarea
                label="Arguments (one per line)"
                value={form.args}
                onChange={(v) => setForm({ ...form, args: v })}
                rows={3}
                placeholder={"-y\n@modelcontextprotocol/server-github"}
              />
              <Textarea
                label="Environment (KEY=VALUE per line)"
                value={form.env}
                onChange={(v) => setForm({ ...form, env: v })}
                rows={3}
                placeholder="GITHUB_TOKEN=ghp_..."
              />
            </>
          ) : (
            <>
              <Input
                label="URL"
                value={form.url}
                onChange={(v) => setForm({ ...form, url: v })}
                placeholder="https://mcp.example.com/mcp"
              />
              <Textarea
                label="Headers (KEY=VALUE per line)"
                value={form.headers}
                onChange={(v) => setForm({ ...form, headers: v })}
                rows={3}
                placeholder="Authorization=Bearer ..."
              />
            </>
          )}
        </div>
        <div className="hstack mt14">
          <Button
            variant="primary"
            disabled={!form.name.trim() || (stdio ? !form.command.trim() : !form.url.trim())}
            onClick={save}
          >
            {editingId != null ? "Save changes" : "Add connector"}
          </Button>
          {editingId != null && (
            <Button variant="ghost" onClick={reset}>
              Cancel
            </Button>
          )}
        </div>
      </Card>

      {s.claudeConnectors.length === 0 && <div className="empty">No connectors yet.</div>}

      {s.claudeConnectors.map((c) => (
        <Card key={c.id}>
          <div className="card-head">
            <span className="mono" style={{ fontWeight: "var(--fw-bold)", fontSize: "var(--text-lg)", color: "var(--text-heading)" }}>
              {c.name}
            </span>
            <div className="hstack">
              <Badge tone="info">{c.transport}</Badge>
              <Badge tone={c.enabled ? "success" : "neutral"}>
                {c.enabled ? "enabled" : "disabled"}
              </Badge>
              <Toggle on={c.enabled} onClick={() => s.updateClaudeConnector(c.id, { enabled: !c.enabled })} />
              <Button size="sm" variant="secondary" onClick={() => edit(c)}>
                Edit
              </Button>
              <Button size="sm" variant="danger" onClick={() => s.deleteClaudeConnector(c.id)}>
                Remove
              </Button>
            </div>
          </div>
          <div className="mono faint" style={{ fontSize: "var(--text-xs)", marginTop: 8 }}>
            {c.transport === "stdio"
              ? [c.command, ...(c.args ?? [])].join(" ")
              : c.url}
          </div>
        </Card>
      ))}
    </>
  );
}

/* ---- Plugins ----------------------------------------------------------------------- */

const emptyPlugin = { name: "", marketplace: "", marketplace_repo: "", enabled: true };

function PluginsPanel() {
  const s = useDashboard();
  const [form, setForm] = useState(emptyPlugin);
  const [editingId, setEditingId] = useState<number | null>(null);

  const reset = () => {
    setForm(emptyPlugin);
    setEditingId(null);
  };

  const save = async () => {
    const body: PluginBody = { ...form };
    const ok =
      editingId != null
        ? await s.updateClaudePlugin(editingId, body)
        : await s.createClaudePlugin(body);
    if (ok) reset();
  };

  const edit = (p: ClaudePlugin) => {
    setForm({
      name: p.name,
      marketplace: p.marketplace,
      marketplace_repo: p.marketplace_repo,
      enabled: p.enabled,
    });
    setEditingId(p.id);
  };

  return (
    <>
      <div className="faint" style={{ fontSize: "var(--text-sm)", marginBottom: 14 }}>
        Claude Code plugins, pinned to the marketplace serving them. Generated settings
        declare the marketplace and enable the plugin, so headless runs install both on
        boot.
      </div>
      <Card>
        <div className="card-head" style={{ marginBottom: 14 }}>
          <span className="card-title" style={{ fontSize: "var(--text-md)", color: "var(--text-heading)" }}>
            {editingId != null ? `Edit plugin · ${form.name}` : "Add a plugin"}
          </span>
        </div>
        <div className="form-grid">
          <Input
            label="Plugin name"
            value={form.name}
            onChange={(v) => setForm({ ...form, name: v })}
            placeholder="code-reviewer"
          />
          <Input
            label="Marketplace key"
            value={form.marketplace}
            onChange={(v) => setForm({ ...form, marketplace: v })}
            placeholder="acme-tools"
          />
          <Input
            label="Marketplace repo (owner/repo or git URL)"
            value={form.marketplace_repo}
            onChange={(v) => setForm({ ...form, marketplace_repo: v })}
            placeholder="acme/claude-marketplace"
          />
        </div>
        <div className="hstack mt14">
          <Button
            variant="primary"
            disabled={!form.name.trim() || !form.marketplace.trim() || !form.marketplace_repo.trim()}
            onClick={save}
          >
            {editingId != null ? "Save changes" : "Add plugin"}
          </Button>
          {editingId != null && (
            <Button variant="ghost" onClick={reset}>
              Cancel
            </Button>
          )}
        </div>
      </Card>

      {s.claudePlugins.length === 0 && <div className="empty">No plugins yet.</div>}

      {s.claudePlugins.map((p) => (
        <Card key={p.id}>
          <div className="card-head">
            <span className="mono" style={{ fontWeight: "var(--fw-bold)", fontSize: "var(--text-lg)", color: "var(--text-heading)" }}>
              {p.name}@{p.marketplace}
            </span>
            <div className="hstack">
              <Badge tone={p.enabled ? "success" : "neutral"}>
                {p.enabled ? "enabled" : "disabled"}
              </Badge>
              <Toggle on={p.enabled} onClick={() => s.updateClaudePlugin(p.id, { enabled: !p.enabled })} />
              <Button size="sm" variant="secondary" onClick={() => edit(p)}>
                Edit
              </Button>
              <Button size="sm" variant="danger" onClick={() => s.deleteClaudePlugin(p.id)}>
                Remove
              </Button>
            </div>
          </div>
          <div className="mono faint" style={{ fontSize: "var(--text-xs)", marginTop: 8 }}>
            {p.marketplace_repo}
          </div>
        </Card>
      ))}
    </>
  );
}

/* ---- Permissions ------------------------------------------------------------------- */

const MODE_OPTS = [
  { value: "", label: "(keep server baseline)" },
  { value: "default", label: "default" },
  { value: "acceptEdits", label: "acceptEdits" },
  { value: "plan", label: "plan" },
  { value: "bypassPermissions", label: "bypassPermissions" },
];

function PermissionsPanel() {
  const s = useDashboard();
  const p = s.claudePermissions;
  const [form, setForm] = useState<{ mode: string; allow: string; deny: string; ask: string } | null>(null);

  // Seed the form from the loaded permissions once; afterwards the operator's draft wins.
  if (form === null && p !== null) {
    setForm({
      mode: p.default_mode ?? "",
      allow: p.allow.join("\n"),
      deny: p.deny.join("\n"),
      ask: p.ask.join("\n"),
    });
    return null;
  }
  if (form === null || p === null) {
    return <div className="empty">Loading permissions…</div>;
  }

  const save = () =>
    s.saveClaudePermissions({
      default_mode: form.mode || null,
      allow: parseLines(form.allow),
      deny: parseLines(form.deny),
      ask: parseLines(form.ask),
    });

  return (
    <>
      <div className="faint" style={{ fontSize: "var(--text-sm)", marginBottom: 14 }}>
        Overrides merged over the server baseline into every generated{" "}
        <span className="mono">settings.json</span>. Headless runs auto-deny anything that
        would prompt, so allow rules are what let work proceed; the PreToolUse/Stop hooks
        stay the hard gate regardless.
      </div>
      <Card>
        <div className="form-grid">
          <Select
            label={`Default mode (baseline: ${p.base_mode})`}
            value={form.mode}
            onChange={(v) => setForm({ ...form, mode: v })}
            options={MODE_OPTS}
          />
          <div className="field">
            <span className="field-label">Baseline allow rules (from server env)</span>
            <div className="mono faint" style={{ fontSize: "var(--text-xs)", padding: "6px 0" }}>
              {p.base_allow.length ? p.base_allow.join("  ·  ") : "—"}
            </div>
          </div>
          <Textarea
            label="Extra allow rules (one per line)"
            value={form.allow}
            onChange={(v) => setForm({ ...form, allow: v })}
            rows={4}
            placeholder={"Bash(npm *)\nWebFetch(domain:docs.example.com)"}
          />
          <Textarea
            label="Deny rules (one per line)"
            value={form.deny}
            onChange={(v) => setForm({ ...form, deny: v })}
            rows={4}
            placeholder={"Bash(rm -rf *)\nRead(./secrets/**)"}
          />
          <Textarea
            label="Ask rules (one per line — headless runs deny these)"
            value={form.ask}
            onChange={(v) => setForm({ ...form, ask: v })}
            rows={4}
            placeholder="Bash(git push *)"
          />
        </div>
        <div className="hstack mt14">
          <Button variant="primary" onClick={save}>
            Save permissions
          </Button>
        </div>
      </Card>
    </>
  );
}

/* ---- The page ---------------------------------------------------------------------- */

const TABS = [
  { value: "account", label: "Account" },
  { value: "skills", label: "Skills" },
  { value: "connectors", label: "Connectors" },
  { value: "plugins", label: "Plugins" },
  { value: "permissions", label: "Permissions" },
];

export function ClaudeSection() {
  const [tab, setTab] = useState("account");

  return (
    <>
      <div className="section-head">
        <div className="section-title">Claude</div>
        <div className="section-desc">
          Manage the Claude Code install agents run on: the account login, plus skills,
          MCP connectors, plugins, and permissions. Changes apply to the next launch of
          every agent.
        </div>
      </div>
      <div className="section-body">
        <div style={{ marginBottom: 16 }}>
          <Tabs tabs={TABS} value={tab} onChange={setTab} />
        </div>
        {tab === "account" && <ClaudeLoginPanel />}
        {tab === "skills" && <SkillsPanel />}
        {tab === "connectors" && <ConnectorsPanel />}
        {tab === "plugins" && <PluginsPanel />}
        {tab === "permissions" && <PermissionsPanel />}
      </div>
    </>
  );
}
