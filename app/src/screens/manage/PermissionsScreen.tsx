import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { radius, text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Button } from "../../components/Button";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { Select } from "../../components/Select";
import { TextField } from "../../components/TextField";
import { Card, Mono, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import type { ClaudePermissions } from "../../api/client";

/**
 * Permissions — the stored overrides merged over the server's env baseline into
 * every generated settings.json, the mobile counterpart of the web dashboard's
 * PermissionsPanel. Headless runs auto-deny anything that would prompt, so
 * allow rules are what let work proceed.
 */

const MODE_OPTIONS = [
  { value: "", label: "(keep server baseline)" },
  { value: "default", label: "default" },
  { value: "acceptEdits", label: "acceptEdits" },
  { value: "plan", label: "plan" },
  { value: "bypassPermissions", label: "bypassPermissions" },
];

interface Draft {
  mode: string;
  allow: string;
  deny: string;
  ask: string;
}

/* One rule per line → trimmed, blank-free list. */
function parseLines(s: string): string[] {
  return s
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

export function PermissionsScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();

  const { data, error: loadError, loading, reload } =
    useResource<ClaudePermissions>("/claude/permissions");

  const [form, setForm] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Seed the form from the loaded permissions once; afterwards the operator's draft wins.
  useEffect(() => {
    if (form === null && data !== null) {
      setForm({
        mode: data.default_mode ?? "",
        allow: data.allow.join("\n"),
        deny: data.deny.join("\n"),
        ask: data.ask.join("\n"),
      });
    }
  }, [data, form]);

  async function save() {
    if (!client || !form) return;
    setError(null);
    setBusy(true);
    try {
      await client.api<ClaudePermissions>("/claude/permissions", {
        method: "PUT",
        body: {
          default_mode: form.mode || null,
          allow: parseLines(form.allow),
          deny: parseLines(form.deny),
          ask: parseLines(form.ask),
        },
      });
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t save permissions.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ManageShell
      title="Permissions"
      subtitle="Overrides merged over the server baseline into every generated settings.json."
    >
      <ErrorNotice message={error ?? loadError} />

      {data === null || form === null ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          {loading ? "Loading permissions…" : "Permissions unavailable."}
        </Text>
      ) : (
        <>
          <View
            style={[
              styles.baseline,
              {
                backgroundColor: colors.surfaceSunken,
                borderColor: colors.borderSubtle,
              },
            ]}
          >
            <SectionLabel style={{ marginBottom: 8 }}>
              Server baseline (env)
            </SectionLabel>
            <Mono style={{ fontSize: 12, color: colors.textMuted }}>
              {`mode: ${data.base_mode}`}
            </Mono>
            {data.base_allow.length > 0 ? (
              data.base_allow.map((rule) => (
                <Mono key={rule} style={{ fontSize: 12, color: colors.textMuted }}>
                  {rule}
                </Mono>
              ))
            ) : (
              <Mono style={{ fontSize: 12, color: colors.textMuted }}>
                (no baseline allow rules)
              </Mono>
            )}
          </View>

          <Card style={{ padding: 16, gap: 14 }}>
            <Select
              label="Default mode"
              options={MODE_OPTIONS}
              value={form.mode}
              onChange={(v) => setForm({ ...form, mode: v })}
            />
            <Field label="Allow" hint="One rule per line, e.g. Bash(npm run *)">
              <TextField
                value={form.allow}
                onChangeText={(v) => setForm({ ...form, allow: v })}
                placeholder={"Bash(npm *)\nWebFetch(domain:docs.example.com)"}
                multiline
                height={90}
                autoCapitalize="none"
                autoCorrect={false}
              />
            </Field>
            <Field label="Deny" hint="One rule per line, e.g. Read(./secrets/**)">
              <TextField
                value={form.deny}
                onChangeText={(v) => setForm({ ...form, deny: v })}
                placeholder={"Bash(rm -rf *)\nRead(./secrets/**)"}
                multiline
                height={90}
                autoCapitalize="none"
                autoCorrect={false}
              />
            </Field>
            <Field label="Ask" hint="One rule per line — headless runs deny these.">
              <TextField
                value={form.ask}
                onChangeText={(v) => setForm({ ...form, ask: v })}
                placeholder="Bash(git push *)"
                multiline
                height={90}
                autoCapitalize="none"
                autoCorrect={false}
              />
            </Field>
            <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : save}>
              {busy ? "Saving…" : "Save permissions"}
            </Button>
          </Card>
        </>
      )}
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  baseline: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
    marginBottom: 16,
    gap: 2,
  },
});
