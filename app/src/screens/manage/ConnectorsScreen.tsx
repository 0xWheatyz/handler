import React, { useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Select } from "../../components/Select";
import { Switch } from "../../components/Switch";
import { TextField } from "../../components/TextField";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { Card, Divider, Mono, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import type { ClaudeConnector, McpTransport } from "../../api/client";

/**
 * Connectors — MCP servers agents may reach, the mobile counterpart of the web
 * dashboard's Claude → Connectors panel. Rows become each run's --mcp-config
 * file at the next launch (stdio commands run inside the control container).
 * Everyone sees the shared rows (owner NULL) plus their own; mutating a row the
 * session doesn't own 403s server-side and surfaces inline, never fatally.
 */

const TRANSPORT_OPTIONS = [
  { value: "stdio", label: "stdio (run a command)" },
  { value: "http", label: "http (remote server)" },
  { value: "sse", label: "sse (remote server, legacy)" },
];

/* "KEY=value per line" → map; blank and =-less lines are dropped, not errors. */
function parseEnvLines(input: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of input.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    out[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim();
  }
  return out;
}

/* "Name: value per line" → map; same lenient skipping as env parsing. */
function parseHeaderLines(input: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of input.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const colon = trimmed.indexOf(":");
    if (colon <= 0) continue;
    out[trimmed.slice(0, colon).trim()] = trimmed.slice(colon + 1).trim();
  }
  return out;
}

export function ConnectorsScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();
  const {
    data,
    error: loadError,
    loading,
    reload,
  } = useResource<ClaudeConnector[]>("/claude/connectors");
  const connectors = data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [transport, setTransport] = useState<McpTransport>("stdio");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [env, setEnv] = useState("");
  const [url, setUrl] = useState("");
  const [headers, setHeaders] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stdio = transport === "stdio";

  async function create() {
    if (!client) return;
    if (!name.trim()) {
      setError("A connector name is required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      // The server 422s a stdio connector without a command / an http(s)-less
      // remote url, so mismatched fields surface inline instead of client-side.
      await client.api<ClaudeConnector>("/claude/connectors", {
        body: {
          name: name.trim(),
          transport,
          command: stdio ? command.trim() || null : null,
          args: stdio ? args.trim().split(/\s+/).filter(Boolean) : [],
          env: stdio ? parseEnvLines(env) : {},
          url: stdio ? null : url.trim() || null,
          headers: stdio ? {} : parseHeaderLines(headers),
          enabled: true,
        },
      });
      setName("");
      setCommand("");
      setArgs("");
      setEnv("");
      setUrl("");
      setHeaders("");
      setShowForm(false);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t create the connector.");
    } finally {
      setBusy(false);
    }
  }

  function toggle(c: ClaudeConnector, enabled: boolean) {
    if (!client) return;
    client
      .api(`/claude/connectors/${c.id}`, { method: "PATCH", body: { enabled } })
      .then(reload)
      .catch((e) => setError(e instanceof Error ? e.message : "Update failed."));
  }

  function confirmDelete(c: ClaudeConnector) {
    Alert.alert(
      "Delete connector?",
      `Agents lose ${c.name} at their next launch. This can’t be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            client
              ?.api(`/claude/connectors/${c.id}`, { method: "DELETE" })
              .then(reload)
              .catch((e) =>
                setError(e instanceof Error ? e.message : "Delete failed."),
              );
          },
        },
      ],
    );
  }

  return (
    <ManageShell
      title="Connectors"
      subtitle="MCP servers agents can reach — passed to each run as its --mcp-config file, so nothing lands in the repository tree."
    >
      <View style={styles.headRow}>
        <SectionLabel>
          {loading
            ? "Loading…"
            : `${connectors.length} connector${connectors.length === 1 ? "" : "s"}`}
        </SectionLabel>
        <Button
          size="sm"
          variant={showForm ? "secondary" : "primary"}
          onPress={() => setShowForm((v) => !v)}
        >
          {showForm ? "Cancel" : "New"}
        </Button>
      </View>

      {showForm ? (
        <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
          <Field label="Name">
            <TextField
              value={name}
              onChangeText={setName}
              placeholder="github"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Select
            label="Transport"
            options={TRANSPORT_OPTIONS}
            value={transport}
            onChange={(v) => setTransport(v as McpTransport)}
          />
          {stdio ? (
            <>
              <Field label="Command" hint="Runs inside the control container.">
                <TextField
                  value={command}
                  onChangeText={setCommand}
                  placeholder="npx"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </Field>
              <Field label="Arguments" hint="Space-separated.">
                <TextField
                  value={args}
                  onChangeText={setArgs}
                  placeholder="-y @modelcontextprotocol/server-github"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </Field>
              <Field label="Environment" hint="KEY=value per line.">
                <TextField
                  value={env}
                  onChangeText={setEnv}
                  placeholder={"GITHUB_TOKEN=ghp_..."}
                  multiline
                  height={80}
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </Field>
            </>
          ) : (
            <>
              <Field label="URL">
                <TextField
                  value={url}
                  onChangeText={setUrl}
                  placeholder="https://mcp.example.com/mcp"
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                />
              </Field>
              <Field label="Headers" hint="Name: value per line.">
                <TextField
                  value={headers}
                  onChangeText={setHeaders}
                  placeholder={"Authorization: Bearer ..."}
                  multiline
                  height={80}
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </Field>
            </>
          )}
          <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : create}>
            {busy ? "Creating…" : "Add connector"}
          </Button>
        </Card>
      ) : null}

      <ErrorNotice message={error ?? loadError} />

      {connectors.length === 0 && !loading ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          No connectors yet.
        </Text>
      ) : (
        <Card>
          {connectors.map((c, i) => (
            <View key={c.id}>
              {i > 0 && <Divider />}
              <View style={styles.row}>
                <View style={{ flex: 1, gap: 4 }}>
                  <View style={styles.titleRow}>
                    <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                      {c.name}
                    </Mono>
                    <Badge tone="neutral">{c.transport}</Badge>
                    {c.owner_user_id != null ? (
                      <Badge tone="neutral">private</Badge>
                    ) : null}
                  </View>
                  <Mono
                    numberOfLines={2}
                    style={{ fontSize: 12, color: colors.textMuted }}
                  >
                    {c.transport === "stdio"
                      ? [c.command ?? "", ...(c.args ?? [])].join(" ").trim()
                      : c.url ?? ""}
                  </Mono>
                </View>
                <View style={styles.rowActions}>
                  <Switch value={c.enabled} onValueChange={(v) => toggle(c, v)} />
                  <Button size="sm" variant="danger" onPress={() => confirmDelete(c)}>
                    Delete
                  </Button>
                </View>
              </View>
            </View>
          ))}
        </Card>
      )}
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  headRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  row: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  rowActions: {
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: 10,
  },
});
