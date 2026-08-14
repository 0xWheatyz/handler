import React, { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Badge } from "../components/Badge";
import { Chip } from "../components/Chip";
import { Icon } from "../components/Icon";
import { PageHeader } from "../components/PageHeader";
import { Card, Divider, Mono, SectionLabel } from "../components/primitives";
import { useAppState, type AgentFilter } from "../state/AppState";
import { statusLabel, statusTone, timeAgo } from "../api/format";
import type { Agent } from "../api/client";

/**
 * The full agent roster, reached by tapping a fleet stat card. Unlike the fleet's
 * "Recent checkmarks" list this shows every agent row the API knows — an agent that
 * hasn't dropped a checkmark yet is still visible here the moment it spawns. The
 * filter buckets use exactly the same grouping as the stat-card counts, so the
 * number tapped is the number listed.
 */

const FILTERS: { key: AgentFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "running", label: "Running" },
  { key: "waiting", label: "Waiting" },
  { key: "done", label: "Done" },
];

function isRunning(a: Agent): boolean {
  const s = a.status.toLowerCase();
  return s === "working" || s === "running";
}

function isDone(a: Agent): boolean {
  const s = a.status.toLowerCase();
  return s === "done" || s === "failed";
}

export function AgentListScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { go, openDetail, agents, waiting, agentFilter, setAgentFilter } =
    useAppState();

  // Waiting matches the fleet's "waiting on you" derivation (paused agents plus
  // open checkmark questions), keyed the same way the store builds it.
  const waitingKeys = useMemo(
    () => new Set(waiting.map((w) => `${w.project}/${w.name}`)),
    [waiting],
  );

  const rows = useMemo(() => {
    switch (agentFilter) {
      case "running":
        return agents.filter(isRunning);
      case "waiting":
        return agents.filter((a) => waitingKeys.has(`${a.project_id}/${a.name}`));
      case "done":
        return agents.filter(isDone);
      default:
        return agents;
    }
  }, [agents, agentFilter, waitingKeys]);

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <View style={styles.header}>
        <PageHeader leading="back" onLeadingPress={() => go("fleet")} title="Agents" />
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filters}
        >
          {FILTERS.map((f) => (
            <Chip
              key={f.key}
              label={f.label}
              selected={agentFilter === f.key}
              onPress={() => setAgentFilter(f.key)}
            />
          ))}
        </ScrollView>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + 24 }]}
        showsVerticalScrollIndicator={false}
      >
        <SectionLabel style={{ marginBottom: 8 }}>
          {`${rows.length} agent${rows.length === 1 ? "" : "s"}`}
        </SectionLabel>
        {rows.length === 0 ? (
          <Text style={[text.bodySm, { color: colors.textMuted }]}>
            {agentFilter === "all"
              ? "No agents yet — spawn one from the Fleet screen."
              : `No ${agentFilter} agents right now.`}
          </Text>
        ) : (
          <Card>
            {rows.map((a, i) => (
              <View key={`${a.project_id}/${a.name}`}>
                {i > 0 && <Divider />}
                <Pressable
                  style={({ pressed }) => [
                    styles.row,
                    pressed && { backgroundColor: colors.surfaceSunken },
                  ]}
                  onPress={() => openDetail(a.project_id, a.name, "agentList")}
                >
                  <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
                    <View style={styles.titleRow}>
                      <Mono style={{ fontSize: 13, color: colors.textHeading }}>
                        {a.name}
                      </Mono>
                      <Badge tone={statusTone(a.status)}>{statusLabel(a.status)}</Badge>
                    </View>
                    <Text style={[text.caption, { color: colors.textMuted }]}>
                      {a.project_id}
                      {a.role ? ` · ${a.role}` : ""}
                      {` · started ${timeAgo(a.created_at)} ago`}
                    </Text>
                    {a.last_output?.trim() && isRunning(a) ? (
                      <Mono
                        numberOfLines={1}
                        style={{ fontSize: 11.5, color: colors.textMuted }}
                      >
                        {a.last_output.trim().split("\n").pop()}
                      </Mono>
                    ) : null}
                  </View>
                  <Icon name="chevronRight" size={16} color={colors.ink4} />
                </Pressable>
              </View>
            ))}
          </Card>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  header: { paddingTop: 8, paddingHorizontal: 20 },
  filters: { flexDirection: "row", gap: 8, paddingBottom: 12, paddingRight: 20 },
  body: { paddingHorizontal: 20 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 44,
  },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" },
});
