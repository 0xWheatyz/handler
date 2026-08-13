import React, { useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { radius, text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Switch } from "../../components/Switch";
import { TextField } from "../../components/TextField";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { Card, Divider, Mono, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import type { ClaudeSkill, Command } from "../../api/client";

/**
 * Skills — managed Claude Code skills, the mobile counterpart of the web
 * dashboard's Claude → Skills panel. Rows are plain DB writes the control
 * container syncs to every worker's ~/.claude/skills at the next agent launch.
 * Everyone sees the shared rows (owner NULL) plus their own; mutating a row the
 * session doesn't own 403s server-side and surfaces inline, never fatally.
 */

export function SkillsScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();
  const {
    data,
    error: loadError,
    loading,
    reload,
  } = useResource<ClaudeSkill[]>("/claude/skills");
  const skills = data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [installPrompt, setInstallPrompt] = useState("");
  const [installing, setInstalling] = useState(false);
  const [installError, setInstallError] = useState<string | null>(null);
  const [installSummary, setInstallSummary] = useState<string | null>(null);

  async function create() {
    if (!client) return;
    if (!name.trim() || !content.trim()) {
      setError("Name and content are both required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await client.api<ClaudeSkill>("/claude/skills", {
        body: {
          name: name.trim(),
          description: description.trim() || null,
          content,
          enabled: true,
        },
      });
      setName("");
      setDescription("");
      setContent("");
      setShowForm(false);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t create the skill.");
    } finally {
      setBusy(false);
    }
  }

  function toggle(sk: ClaudeSkill, enabled: boolean) {
    if (!client) return;
    client
      .api(`/claude/skills/${sk.id}`, { method: "PATCH", body: { enabled } })
      .then(reload)
      .catch((e) => setError(e instanceof Error ? e.message : "Update failed."));
  }

  function confirmDelete(sk: ClaudeSkill) {
    Alert.alert(
      "Delete skill?",
      `Remove ${sk.name} from every worker at its next launch. This can’t be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            client
              ?.api(`/claude/skills/${sk.id}`, { method: "DELETE" })
              .then(reload)
              .catch((e) =>
                setError(e instanceof Error ? e.message : "Delete failed."),
              );
          },
        },
      ],
    );
  }

  /* Install-from-prompt runs headlessly on the worker — the 202 hands back a
   * command we poll to completion (installs can be slow: network + a full
   * claude run, hence the 4-minute budget). */
  async function install() {
    if (!client || !installPrompt.trim()) return;
    setInstallError(null);
    setInstallSummary(null);
    setInstalling(true);
    try {
      const cmd = await client.api<Command>("/claude/skills/install", {
        body: { prompt: installPrompt.trim() },
      });
      const done = await client.trackCommand(cmd.id, {
        attempts: 120,
        intervalMs: 2000,
      });
      if (done === null) {
        setInstallError(
          "Still installing after 4 minutes — pull to reload later to see what landed.",
        );
      } else if (done.status === "failed") {
        setInstallError(done.error ?? "Install failed.");
      } else {
        setInstallSummary(
          done.result ? JSON.stringify(done.result).trim() : "Installed.",
        );
        setInstallPrompt("");
        reload();
      }
    } catch (e) {
      setInstallError(e instanceof Error ? e.message : "Install failed.");
    } finally {
      setInstalling(false);
    }
  }

  return (
    <ManageShell
      title="Skills"
      subtitle="Managed skills, synced to every worker’s ~/.claude/skills at each agent launch. The description is what makes Claude pick a skill up."
    >
      <View style={styles.headRow}>
        <SectionLabel>
          {loading
            ? "Loading…"
            : `${skills.length} skill${skills.length === 1 ? "" : "s"}`}
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
          <Field label="Name" hint="A slug — becomes the skill directory.">
            <TextField
              value={name}
              onChangeText={setName}
              placeholder="deploy-checklist"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Field label="Description" hint="When should Claude use it? (optional)">
            <TextField
              value={description}
              onChangeText={setDescription}
              placeholder="Use when preparing or reviewing a deploy."
            />
          </Field>
          <Field label="SKILL.md body">
            <TextField
              value={content}
              onChangeText={setContent}
              placeholder={"# Deploy checklist\n\n1. ..."}
              multiline
              height={160}
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : create}>
            {busy ? "Creating…" : "Add skill"}
          </Button>
        </Card>
      ) : null}

      <SectionLabel style={{ marginBottom: 8 }}>Install from a marketplace prompt</SectionLabel>
      <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
        <Field
          label="Install prompt"
          hint="Runs headlessly on the worker — when the instructions offer choices, Claude picks the defaults (always user scope). Review the imported skill below afterwards."
        >
          <TextField
            value={installPrompt}
            onChangeText={setInstallPrompt}
            placeholder="Paste the whole prompt the marketplace page tells you to give Claude."
            multiline
            height={100}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </Field>
        <Button
          size="lg"
          style={{ width: "100%" }}
          onPress={installing || !installPrompt.trim() ? undefined : install}
        >
          {installing ? "Installing…" : "Run install"}
        </Button>
        {installSummary ? (
          <Mono style={{ fontSize: 12, color: colors.positive }} numberOfLines={4}>
            {installSummary}
          </Mono>
        ) : null}
        <ErrorNotice message={installError} />
      </Card>

      <ErrorNotice message={error ?? loadError} />

      {skills.length === 0 && !loading ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          No custom skills yet.
        </Text>
      ) : (
        <Card>
          {skills.map((sk, i) => {
            const expanded = expandedId === sk.id;
            return (
              <View key={sk.id}>
                {i > 0 && <Divider />}
                <Pressable
                  style={styles.row}
                  onPress={() => setExpandedId(expanded ? null : sk.id)}
                >
                  <View style={{ flex: 1, gap: 4 }}>
                    <View style={styles.titleRow}>
                      <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                        {sk.name}
                      </Mono>
                      {sk.owner_user_id != null ? (
                        <Badge tone="neutral">private</Badge>
                      ) : null}
                    </View>
                    {sk.description ? (
                      <Text
                        numberOfLines={expanded ? undefined : 2}
                        style={[text.caption, { color: colors.textMuted }]}
                      >
                        {sk.description}
                      </Text>
                    ) : null}
                    {sk.files.length > 0 ? (
                      <Text style={[text.caption, { color: colors.textMuted }]}>
                        ships with {sk.files.length} file
                        {sk.files.length === 1 ? "" : "s"}
                      </Text>
                    ) : null}
                  </View>
                  <View style={styles.rowActions}>
                    <Switch value={sk.enabled} onValueChange={(v) => toggle(sk, v)} />
                    <Button size="sm" variant="danger" onPress={() => confirmDelete(sk)}>
                      Delete
                    </Button>
                  </View>
                </Pressable>
                {expanded ? (
                  <View style={styles.detail}>
                    <View
                      style={[
                        styles.monoBlock,
                        {
                          backgroundColor: colors.surfaceSunken,
                          borderColor: colors.borderSubtle,
                        },
                      ]}
                    >
                      <Mono style={{ fontSize: 12, color: colors.textBody }}>
                        {sk.content}
                      </Mono>
                    </View>
                    {sk.files.map((f) => (
                      <Mono
                        key={f}
                        style={{ fontSize: 12, color: colors.textMuted }}
                        numberOfLines={1}
                      >
                        {f}
                      </Mono>
                    ))}
                  </View>
                ) : null}
              </View>
            );
          })}
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
  detail: {
    paddingHorizontal: 16,
    paddingBottom: 12,
    gap: 6,
  },
  monoBlock: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
  },
});
