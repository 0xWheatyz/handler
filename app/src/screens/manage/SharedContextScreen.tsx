import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { radius, text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Button } from "../../components/Button";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { TextField } from "../../components/TextField";
import { Card, Divider, Mono, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import { timeAgo } from "../../api/format";
import type { SharedContext } from "../../api/client";

/**
 * Shared context — the cross-project key/value store every agent can read
 * (README 3.4). Reads use the normal token; writing a key needs the
 * higher-trust shared-context write token, so a normal or even admin token
 * may 403 — the server's message is surfaced verbatim.
 */

export function SharedContextScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();

  const { data, error: loadError, loading, reload } =
    useResource<SharedContext[]>("/shared/context");

  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function set() {
    if (!client) return;
    if (!key.trim() || !value.trim()) {
      setError("Key and value are both required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await client.api<SharedContext>(
        `/shared/context/${encodeURIComponent(key.trim())}`,
        { method: "PUT", body: { value: value.trim() } },
      );
      setKey("");
      setValue("");
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t set the key.");
    } finally {
      setBusy(false);
    }
  }

  const rows = data ?? [];

  return (
    <ManageShell
      title="Shared context"
      subtitle="Key/value facts every agent across every project can read."
    >
      <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
        <SectionLabel>Set a key</SectionLabel>
        <Field label="Key">
          <TextField
            value={key}
            onChangeText={setKey}
            placeholder="staging_url"
            autoCapitalize="none"
            autoCorrect={false}
          />
        </Field>
        <Field
          label="Value"
          hint="Requires the shared-context write token (or admin/global if unset)."
        >
          <TextField
            value={value}
            onChangeText={setValue}
            placeholder="value"
            multiline
            height={80}
          />
        </Field>
        <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : set}>
          {busy ? "Setting…" : "Set"}
        </Button>
      </Card>

      <ErrorNotice message={error ?? loadError} />

      <SectionLabel style={{ marginBottom: 8 }}>
        {`${rows.length} key${rows.length === 1 ? "" : "s"}`}
      </SectionLabel>

      {rows.length === 0 ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          {loading ? "Loading…" : "No shared context set."}
        </Text>
      ) : (
        <Card>
          {rows.map((c, i) => (
            <View key={c.key}>
              {i > 0 && <Divider />}
              <Pressable
                style={styles.row}
                onPress={() => setExpanded((k) => (k === c.key ? null : c.key))}
              >
                <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                  {c.key}
                </Mono>
                {expanded === c.key ? (
                  <View
                    style={[
                      styles.valueBlock,
                      {
                        backgroundColor: colors.surfaceSunken,
                        borderColor: colors.borderSubtle,
                      },
                    ]}
                  >
                    <Mono style={{ fontSize: 12, color: colors.textBody }}>
                      {c.value}
                    </Mono>
                  </View>
                ) : (
                  <Text
                    numberOfLines={2}
                    style={[text.bodySm, { color: colors.textMuted }]}
                  >
                    {c.value}
                  </Text>
                )}
                <Text style={[text.caption, { color: colors.textMuted }]}>
                  {c.set_by_agent_id != null
                    ? `agent #${c.set_by_agent_id}`
                    : "operator"}
                  {` · updated ${timeAgo(c.updated_at)} ago`}
                </Text>
              </Pressable>
            </View>
          ))}
        </Card>
      )}
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  row: {
    gap: 4,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  valueBlock: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 10,
    marginTop: 2,
  },
});
