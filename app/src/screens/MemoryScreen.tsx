import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Badge } from "../components/Badge";
import { Chip } from "../components/Chip";
import { TabBar } from "../components/TabBar";
import { Card, Divider, Mono, SectionLabel } from "../components/primitives";
import { useAppState, type BadgeTone } from "../state/AppState";
import { timeAgo } from "../api/format";
import type { MemoryNote } from "../api/client";

/**
 * Memory — a read view over the agent-memory note graph (the web dashboard's
 * Memory page). Notes are the distilled facts/decisions/gotchas/runbooks agents
 * leave for each other; tapping a note expands its body, tags, and links.
 * Authoring stays on the web dashboard (admin token) and in the agents' own
 * MCP server — the phone is for looking things up.
 */

const KIND_FILTERS = ["all", "fact", "decision", "gotcha", "runbook"];

const KIND_TONES: Record<string, BadgeTone> = {
  fact: "neutral",
  decision: "positive",
  gotcha: "danger",
  runbook: "warning",
};

export function MemoryScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { memory, memoryError } = useAppState();

  const [kind, setKind] = useState("all");
  const [openId, setOpenId] = useState<number | null>(null);

  const notes = useMemo(() => {
    const all = memory?.notes ?? [];
    const inKind = kind === "all" ? all : all.filter((n) => n.kind === kind);
    return [...inKind].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );
  }, [memory, kind]);

  const byId = useMemo(
    () => new Map((memory?.notes ?? []).map((n) => [n.id, n])),
    [memory],
  );

  /* Both directions of the graph for one note: outgoing "relation → title" and
   * incoming "title → relation". */
  const linksFor = (note: MemoryNote): { key: string; label: string }[] => {
    const links = memory?.links ?? [];
    const out: { key: string; label: string }[] = [];
    for (const l of links) {
      if (l.src_note_id === note.id) {
        out.push({ key: `o${l.id}`, label: `${l.relation} → ${title(byId, l.dst_note_id)}` });
      } else if (l.dst_note_id === note.id) {
        out.push({ key: `i${l.id}`, label: `${title(byId, l.src_note_id)} → ${l.relation}` });
      }
    }
    return out;
  };

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />

      <View style={styles.header}>
        <Text style={[text.h3, { color: colors.textHeading }]}>Memory</Text>
        <Text style={[text.bodySm, { color: colors.textMuted, marginTop: 4 }]}>
          Notes agents distill for every future run. Edit them from the web
          dashboard.
        </Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filters}
        >
          {KIND_FILTERS.map((k) => (
            <Chip
              key={k}
              label={k === "all" ? "All" : k}
              selected={kind === k}
              onPress={() => setKind(k)}
            />
          ))}
        </ScrollView>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.body}
        showsVerticalScrollIndicator={false}
      >
        {memoryError ? (
          <Text style={[text.bodySm, { color: colors.danger }]}>{memoryError}</Text>
        ) : memory === null ? (
          <Text style={[text.bodySm, { color: colors.textMuted }]}>Loading…</Text>
        ) : notes.length === 0 ? (
          <Text style={[text.bodySm, { color: colors.textMuted }]}>
            {kind === "all" ? "No notes yet." : `No ${kind} notes yet.`}
          </Text>
        ) : (
          <>
            <SectionLabel style={{ marginBottom: 8 }}>
              {`${notes.length} note${notes.length === 1 ? "" : "s"}`}
            </SectionLabel>
            <Card>
              {notes.map((n, i) => {
                const open = openId === n.id;
                const links = open ? linksFor(n) : [];
                return (
                  <View key={n.id}>
                    {i > 0 && <Divider />}
                    <Pressable
                      style={styles.row}
                      onPress={() => setOpenId(open ? null : n.id)}
                    >
                      <View style={styles.titleRow}>
                        <Badge tone={KIND_TONES[n.kind] ?? "neutral"}>{n.kind}</Badge>
                        <Text
                          numberOfLines={open ? undefined : 1}
                          style={[text.bodySm, { color: colors.textHeading, flex: 1 }]}
                        >
                          {n.title}
                        </Text>
                      </View>
                      <Text style={[text.caption, { color: colors.textMuted, marginTop: 4 }]}>
                        {n.project_id ?? "global"} · updated {timeAgo(n.updated_at)} ago
                      </Text>

                      {open ? (
                        <View style={{ marginTop: 10, gap: 8 }}>
                          <Text style={[text.bodySm, { color: colors.textBody }]}>
                            {n.body}
                          </Text>
                          {n.tags && n.tags.length > 0 ? (
                            <Mono style={{ fontSize: 12, color: colors.textMuted }}>
                              {n.tags.map((t) => `#${t}`).join("  ")}
                            </Mono>
                          ) : null}
                          {links.length > 0 ? (
                            <View style={{ gap: 4 }}>
                              <SectionLabel>Links</SectionLabel>
                              {links.map((l) => (
                                <Mono
                                  key={l.key}
                                  style={{ fontSize: 12, color: colors.textMuted }}
                                >
                                  {l.label}
                                </Mono>
                              ))}
                            </View>
                          ) : null}
                        </View>
                      ) : null}
                    </Pressable>
                  </View>
                );
              })}
            </Card>
          </>
        )}
      </ScrollView>

      <TabBar active="memory" />
    </View>
  );
}

function title(byId: Map<number, MemoryNote>, id: number): string {
  return byId.get(id)?.title ?? `note #${id}`;
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  header: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 14 },
  filters: { flexDirection: "row", gap: 8, marginTop: 14, paddingRight: 20 },
  body: { paddingHorizontal: 20, paddingBottom: 24 },
  row: { paddingVertical: 12, paddingHorizontal: 16 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
});
