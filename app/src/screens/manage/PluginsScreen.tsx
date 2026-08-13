import React, { useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Switch } from "../../components/Switch";
import { TextField } from "../../components/TextField";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { Card, Divider, Mono, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import type { ClaudePlugin } from "../../api/client";

/**
 * Plugins — Claude Code marketplace plugins, the mobile counterpart of the web
 * dashboard's Claude → Plugins panel. Each row pins a plugin to the marketplace
 * serving it; generated settings declare the marketplace and enable the plugin,
 * so headless runs install both on boot. Everyone sees the shared rows (owner
 * NULL) plus their own; mutating a row the session doesn't own 403s server-side
 * and surfaces inline, never fatally.
 */

export function PluginsScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();
  const {
    data,
    error: loadError,
    loading,
    reload,
  } = useResource<ClaudePlugin[]>("/claude/plugins");
  const plugins = data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [marketplace, setMarketplace] = useState("");
  const [marketplaceRepo, setMarketplaceRepo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    if (!client) return;
    if (!name.trim() || !marketplace.trim() || !marketplaceRepo.trim()) {
      setError("Name, marketplace, and marketplace repo are all required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await client.api<ClaudePlugin>("/claude/plugins", {
        body: {
          name: name.trim(),
          marketplace: marketplace.trim(),
          marketplace_repo: marketplaceRepo.trim(),
          enabled: true,
        },
      });
      setName("");
      setMarketplace("");
      setMarketplaceRepo("");
      setShowForm(false);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t create the plugin.");
    } finally {
      setBusy(false);
    }
  }

  function toggle(p: ClaudePlugin, enabled: boolean) {
    if (!client) return;
    client
      .api(`/claude/plugins/${p.id}`, { method: "PATCH", body: { enabled } })
      .then(reload)
      .catch((e) => setError(e instanceof Error ? e.message : "Update failed."));
  }

  function confirmDelete(p: ClaudePlugin) {
    Alert.alert(
      "Delete plugin?",
      `Runs stop installing ${p.name}@${p.marketplace} at their next launch. This can’t be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            client
              ?.api(`/claude/plugins/${p.id}`, { method: "DELETE" })
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
      title="Plugins"
      subtitle="Claude Code plugins, pinned to the marketplace serving them. Generated settings declare the marketplace and enable the plugin, so headless runs install both on boot."
    >
      <View style={styles.headRow}>
        <SectionLabel>
          {loading
            ? "Loading…"
            : `${plugins.length} plugin${plugins.length === 1 ? "" : "s"}`}
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
          <Field label="Plugin name">
            <TextField
              value={name}
              onChangeText={setName}
              placeholder="code-reviewer"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Field label="Marketplace key">
            <TextField
              value={marketplace}
              onChangeText={setMarketplace}
              placeholder="acme-tools"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Field label="Marketplace repo" hint="owner/repo or a git URL.">
            <TextField
              value={marketplaceRepo}
              onChangeText={setMarketplaceRepo}
              placeholder="acme/claude-marketplace"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : create}>
            {busy ? "Creating…" : "Add plugin"}
          </Button>
        </Card>
      ) : null}

      <ErrorNotice message={error ?? loadError} />

      {plugins.length === 0 && !loading ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          No plugins yet.
        </Text>
      ) : (
        <Card>
          {plugins.map((p, i) => (
            <View key={p.id}>
              {i > 0 && <Divider />}
              <View style={styles.row}>
                <View style={{ flex: 1, gap: 4 }}>
                  <View style={styles.titleRow}>
                    <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                      {`${p.name}@${p.marketplace}`}
                    </Mono>
                    {p.owner_user_id != null ? (
                      <Badge tone="neutral">private</Badge>
                    ) : null}
                  </View>
                  <Mono
                    numberOfLines={1}
                    style={{ fontSize: 12, color: colors.textMuted }}
                  >
                    {p.marketplace_repo}
                  </Mono>
                </View>
                <View style={styles.rowActions}>
                  <Switch value={p.enabled} onValueChange={(v) => toggle(p, v)} />
                  <Button size="sm" variant="danger" onPress={() => confirmDelete(p)}>
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
