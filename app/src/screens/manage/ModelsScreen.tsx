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
import type { ClaudeModel } from "../../api/client";

/**
 * Models — registered model backends, the mobile counterpart of the web
 * dashboard's Claude → Models tab. API keys are write-only server-side:
 * rows only carry has_api_key, so the edit form never prefills the key and
 * offers "new key" / "clear key" verbs instead. Mutations need admin — a
 * non-admin token gets an inline 403, never a sign-out.
 */

const HARNESS_OPTIONS = [
  { value: "claude", label: "claude (Anthropic-compatible endpoint)" },
  { value: "pi", label: "pi (bare OpenAI-compatible endpoint)" },
];

interface FormState {
  name: string;
  baseUrl: string;
  model: string;
  smallFastModel: string;
  harness: "claude" | "pi";
  apiKey: string;
  clearKey: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  baseUrl: "",
  model: "",
  smallFastModel: "",
  harness: "claude",
  apiKey: "",
  clearKey: false,
};

export function ModelsScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();
  const {
    data: models,
    error: loadError,
    loading,
    reload,
  } = useResource<ClaudeModel[]>("/claude/models");

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<ClaudeModel | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  function closeForm() {
    setShowForm(false);
    setEditing(null);
    setForm(EMPTY_FORM);
  }

  function startEdit(m: ClaudeModel) {
    setEditing(m);
    setShowForm(true);
    setError(null);
    setForm({
      name: m.name,
      baseUrl: m.base_url,
      model: m.model,
      smallFastModel: m.small_fast_model ?? "",
      harness: m.harness ?? "claude",
      apiKey: "", // write-only; blank = keep the stored key
      clearKey: false,
    });
  }

  async function save() {
    if (!client) return;
    if (!form.name.trim() || !form.baseUrl.trim() || !form.model.trim()) {
      setError("Name, base URL, and model id are all required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const fields = {
        name: form.name.trim(),
        base_url: form.baseUrl.trim(),
        model: form.model.trim(),
        small_fast_model: form.smallFastModel.trim() || null,
        harness: form.harness,
      };
      if (editing) {
        await client.api(`/claude/models/${editing.id}`, {
          method: "PATCH",
          body: {
            ...fields,
            ...(form.apiKey.trim()
              ? { api_key: form.apiKey.trim() }
              : form.clearKey
                ? { clear_api_key: true }
                : {}),
          },
        });
      } else {
        await client.api("/claude/models", {
          body: {
            ...fields,
            ...(form.apiKey.trim() ? { api_key: form.apiKey.trim() } : {}),
            enabled: true,
          },
        });
      }
      closeForm();
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t save the model.");
    } finally {
      setBusy(false);
    }
  }

  function toggleEnabled(m: ClaudeModel, enabled: boolean) {
    if (!client) return;
    client
      .api(`/claude/models/${m.id}`, { method: "PATCH", body: { enabled } })
      .then(reload)
      .catch((e) => setError(e instanceof Error ? e.message : "Update failed."));
  }

  function confirmDelete(m: ClaudeModel) {
    Alert.alert(
      "Delete model?",
      `Remove ${m.name} from the spawn and schedule forms. This can’t be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            client
              ?.api(`/claude/models/${m.id}`, { method: "DELETE" })
              .then(reload)
              .catch((e) =>
                setError(e instanceof Error ? e.message : "Delete failed."),
              );
          },
        },
      ],
    );
  }

  const list = models ?? [];

  return (
    <ManageShell
      title="Models"
      subtitle="Anthropic-API-compatible model backends the spawn and schedule forms offer next to the Claude subscription."
    >
      <View style={styles.headRow}>
        <SectionLabel>
          {loading
            ? "Loading…"
            : `${list.length} model${list.length === 1 ? "" : "s"}`}
        </SectionLabel>
        <Button
          size="sm"
          variant={showForm ? "secondary" : "primary"}
          onPress={() => {
            if (showForm) closeForm();
            else {
              setError(null);
              setShowForm(true);
            }
          }}
        >
          {showForm ? "Cancel" : "New"}
        </Button>
      </View>

      {showForm ? (
        <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
          {editing ? (
            <Text style={[text.label, { color: colors.textHeading }]}>
              Edit model · {editing.name}
            </Text>
          ) : null}
          <Field label="Name" hint="What the spawn dropdown shows.">
            <TextField
              value={form.name}
              onChangeText={(v) => set({ name: v })}
              placeholder="qwen3-coder"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Field label="Base URL">
            <TextField
              value={form.baseUrl}
              onChangeText={(v) => set({ baseUrl: v })}
              placeholder="http://llm.lan:4000"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
            />
          </Field>
          <Field label="Model" hint="Model id as the endpoint serves it.">
            <TextField
              value={form.model}
              onChangeText={(v) => set({ model: v })}
              placeholder="qwen3-coder-30b"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Field
            label="Small/fast model"
            hint="Optional — defaults to the main model."
          >
            <TextField
              value={form.smallFastModel}
              onChangeText={(v) => set({ smallFastModel: v })}
              placeholder="qwen3-1.7b"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Select
            label="Harness"
            options={HARNESS_OPTIONS}
            value={form.harness}
            onChange={(v) => set({ harness: v as "claude" | "pi" })}
          />
          <Field
            label={editing ? "New API key" : "API key"}
            hint={
              editing
                ? "Optional — blank keeps the stored key. Stored encrypted, never shown again."
                : "Optional. Stored encrypted, never shown again."
            }
          >
            <TextField
              value={form.apiKey}
              onChangeText={(v) => set({ apiKey: v })}
              placeholder="sk-…"
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          {editing?.has_api_key ? (
            <View style={styles.switchRow}>
              <View style={{ flex: 1 }}>
                <Text style={[text.label, { color: colors.textHeading }]}>
                  Clear stored key
                </Text>
                <Text style={[text.caption, { color: colors.textMuted, marginTop: 2 }]}>
                  Drop the stored key on save (ignored if a new key is set).
                </Text>
              </View>
              <Switch
                value={form.clearKey}
                onValueChange={(v) => set({ clearKey: v })}
              />
            </View>
          ) : null}
          <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : save}>
            {busy ? "Saving…" : editing ? "Save changes" : "Create model"}
          </Button>
        </Card>
      ) : null}

      <ErrorNotice message={error ?? loadError} />

      {!loading && list.length === 0 ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          No model backends yet — agents run on the Claude subscription.
        </Text>
      ) : null}

      {list.length > 0 ? (
        <Card>
          {list.map((m, i) => (
            <View key={m.id}>
              {i > 0 && <Divider />}
              <View style={styles.row}>
                <View style={{ flex: 1, gap: 4 }}>
                  <View style={styles.titleRow}>
                    <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                      {m.name}
                    </Mono>
                    {m.harness === "pi" ? (
                      <Badge tone="warning">pi harness</Badge>
                    ) : (
                      <Badge tone="neutral">claude</Badge>
                    )}
                    {m.owner_user_id != null ? (
                      <Badge tone="neutral">private</Badge>
                    ) : null}
                  </View>
                  <Mono style={{ fontSize: 12, color: colors.textHeading }}>
                    {m.model}
                    {m.small_fast_model ? ` (fast: ${m.small_fast_model})` : ""}
                  </Mono>
                  <Mono
                    numberOfLines={1}
                    style={{ fontSize: 12, color: colors.textMuted }}
                  >
                    {m.base_url}
                  </Mono>
                  {m.has_api_key ? (
                    <Text style={[text.caption, { color: colors.textMuted }]}>
                      key stored
                    </Text>
                  ) : null}
                </View>
                <View style={styles.rowActions}>
                  <Switch
                    value={m.enabled}
                    onValueChange={(v) => toggleEnabled(m, v)}
                  />
                  <Button size="sm" variant="secondary" onPress={() => startEdit(m)}>
                    Edit
                  </Button>
                  <Button size="sm" variant="danger" onPress={() => confirmDelete(m)}>
                    Delete
                  </Button>
                </View>
              </View>
            </View>
          ))}
        </Card>
      ) : null}
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
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
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
