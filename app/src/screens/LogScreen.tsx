import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Chip } from "../components/Chip";
import { Mono, SectionLabel } from "../components/primitives";
import { TabBar } from "../components/TabBar";
import { useAppState } from "../state/AppState";
import { clockTime, statusColor } from "../api/format";

export function LogScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { logFilter, setLogFilter, globalLog, projects } = useAppState();

  const filters: { key: string; label: string }[] = [
    { key: "all", label: "All" },
    ...projects.map((p) => ({ key: p.id, label: p.id })),
    { key: "errors", label: "Errors" },
  ];

  const entries = globalLog.filter((e) =>
    logFilter === "all" ? true : logFilter === "errors" ? e.err : e.project === logFilter,
  );

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />

      <View style={styles.header}>
        <Text style={[text.h3, { color: colors.textHeading }]}>Log</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filters}
        >
          {filters.map((f) => (
            <Chip
              key={f.key}
              label={f.label}
              selected={logFilter === f.key}
              onPress={() => setLogFilter(f.key)}
            />
          ))}
        </ScrollView>
      </View>

      <View style={styles.todayLabel}>
        <SectionLabel>Activity</SectionLabel>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={[
          styles.feed,
          { backgroundColor: colors.surfaceSunken, borderTopColor: colors.borderSubtle },
        ]}
        showsVerticalScrollIndicator={false}
      >
        {entries.length === 0 ? (
          <Text style={[text.bodySm, { color: colors.textMuted }]}>No activity yet.</Text>
        ) : (
          entries.map((e) => (
            <View key={e.key} style={styles.logRow}>
              <Mono style={[styles.mono, { color: colors.ink4 }]}>
                {clockTime(e.createdAt)}
              </Mono>
              <Mono
                numberOfLines={1}
                style={[styles.mono, styles.idCol, { color: colors.ink6 }]}
              >
                {e.name}
              </Mono>
              <Mono style={[styles.mono, { color: colors[statusColor(e.status)], flex: 1 }]}>
                {e.msg}
              </Mono>
            </View>
          ))
        )}
      </ScrollView>

      <TabBar active="log" />
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  header: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 16 },
  filters: { flexDirection: "row", gap: 8, marginTop: 14, paddingRight: 20 },
  todayLabel: { paddingHorizontal: 20, paddingBottom: 8 },
  feed: {
    borderTopWidth: 1,
    paddingHorizontal: 20,
    paddingVertical: 16,
    flexGrow: 1,
  },
  logRow: { flexDirection: "row", gap: 10 },
  mono: { fontSize: 12.5, lineHeight: 26 },
  idCol: { width: 86 },
});
