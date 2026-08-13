import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Chip } from "../../components/Chip";
import { ErrorNotice, ManageShell } from "../../components/ManageShell";
import { Card, Divider, Mono, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import { statusLabel, statusTone, timeAgo } from "../../api/format";
import type { Command } from "../../api/client";

/**
 * Activity — the control-command queue: every enqueued action and its status
 * (queued → running → done/failed), the audit log of what the operator triggered.
 * This is the screen that answers "why is my login/spawn/sync stuck": a row stuck
 * `queued` means no worker is claiming; a `failed` row carries the worker's error
 * verbatim. Auto-refreshes while open so a command can be watched to completion.
 */

const FILTERS = ["all", "queued", "running", "failed", "done"];

export function ActivityScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();
  const { data, error, loading, reload } = useResource<Command[]>("/commands?limit=100");

  const [filter, setFilter] = useState("all");
  const [openId, setOpenId] = useState<number | null>(null);
  const [sweepNote, setSweepNote] = useState<string | null>(null);
  const [sweepError, setSweepError] = useState<string | null>(null);

  // The whole point of this screen is watching a command land — poll while open.
  useEffect(() => {
    const id = setInterval(reload, 5000);
    return () => clearInterval(id);
  }, [reload]);

  const commands = (data ?? []).filter((c) =>
    filter === "all" ? true : c.status === filter,
  );

  async function sweepCi() {
    if (!client) return;
    setSweepError(null);
    try {
      await client.api("/poll-ci", { method: "POST" });
      setSweepNote("CI sweep queued.");
      setTimeout(() => setSweepNote(null), 4000);
      reload();
    } catch (e) {
      setSweepError(e instanceof Error ? e.message : "Couldn't queue the sweep.");
    }
  }

  return (
    <ManageShell
      title="Activity"
      subtitle="Control commands the worker drains from the queue. A row stuck on queued means no worker is claiming work."
    >
      <View style={styles.topRow}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filters}
        >
          {FILTERS.map((f) => (
            <Chip
              key={f}
              label={f === "all" ? "All" : statusLabel(f)}
              selected={filter === f}
              onPress={() => setFilter(f)}
            />
          ))}
        </ScrollView>
        <Button size="sm" variant="secondary" onPress={sweepCi}>
          Sweep CI
        </Button>
      </View>

      {sweepNote ? (
        <Text style={[text.caption, { color: colors.positive, marginBottom: 10 }]}>
          {sweepNote}
        </Text>
      ) : null}
      <ErrorNotice message={sweepError ?? error} />

      {loading && data === null ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>Loading…</Text>
      ) : commands.length === 0 ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          {filter === "all" ? "No commands yet." : `No ${filter} commands.`}
        </Text>
      ) : (
        <>
          <SectionLabel style={{ marginBottom: 8 }}>
            {`${commands.length} command${commands.length === 1 ? "" : "s"} · refreshes every 5s`}
          </SectionLabel>
          <Card>
            {commands.map((c, i) => {
              const open = openId === c.id;
              const detail = c.error || (c.result ? JSON.stringify(c.result) : null);
              return (
                <View key={c.id}>
                  {i > 0 && <Divider />}
                  <Pressable
                    style={styles.row}
                    onPress={() => setOpenId(open ? null : c.id)}
                  >
                    <View style={styles.titleRow}>
                      <Mono style={{ fontSize: 13, color: colors.textHeading }}>
                        {c.type}
                      </Mono>
                      <Badge tone={statusTone(c.status)}>{statusLabel(c.status)}</Badge>
                      <Text style={[text.caption, { color: colors.textMuted, marginLeft: "auto" }]}>
                        {timeAgo(c.created_at)}
                      </Text>
                    </View>
                    <Text style={[text.caption, { color: colors.textMuted, marginTop: 2 }]}>
                      {c.project_id ?? "—"}
                      {c.agent_name ? ` · ${c.agent_name}` : ""}
                      {c.claimed_by ? ` · on ${c.claimed_by}` : " · unclaimed"}
                    </Text>
                    {detail ? (
                      <Mono
                        numberOfLines={open ? undefined : 1}
                        style={{
                          fontSize: 12,
                          lineHeight: 17,
                          marginTop: 4,
                          color: c.error ? colors.danger : colors.textMuted,
                        }}
                      >
                        {detail}
                      </Mono>
                    ) : null}
                  </Pressable>
                </View>
              );
            })}
          </Card>
        </>
      )}
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 14,
  },
  filters: { flexDirection: "row", gap: 8, paddingRight: 10 },
  row: { paddingVertical: 12, paddingHorizontal: 16 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" },
});
