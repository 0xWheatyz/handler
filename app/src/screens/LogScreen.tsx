import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Chip } from "../components/Chip";
import { Mono, SectionLabel } from "../components/primitives";
import { TabBar } from "../components/TabBar";
import { useAppState, type LogFilter } from "../state/AppState";
import { allLog } from "../data/mock";

const FILTERS: { key: LogFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "handler", label: "handler" },
  { key: "errors", label: "Errors" },
];

export function LogScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { logFilter, setLogFilter } = useAppState();

  const entries = allLog.filter((e) =>
    logFilter === "all" ? true : logFilter === "errors" ? e.err : e.p === "handler"
  );

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />

      <View style={styles.header}>
        <Text style={[text.h3, { color: colors.textHeading }]}>Log</Text>
        <View style={styles.filters}>
          {FILTERS.map((f) => (
            <Chip
              key={f.key}
              label={f.label}
              selected={logFilter === f.key}
              onPress={() => setLogFilter(f.key)}
            />
          ))}
        </View>
      </View>

      <View style={styles.todayLabel}>
        <SectionLabel>Today</SectionLabel>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={[
          styles.feed,
          { backgroundColor: colors.surfaceSunken, borderTopColor: colors.borderSubtle },
        ]}
        showsVerticalScrollIndicator={false}
      >
        {entries.map((e, i) => (
          <View key={`${e.t}-${i}`} style={styles.logRow}>
            <Mono style={[styles.mono, { color: colors.ink4 }]}>{e.t}</Mono>
            <Mono style={[styles.mono, styles.idCol, { color: colors.ink6 }]}>
              {e.id}
            </Mono>
            <Mono style={[styles.mono, { color: colors[e.color], flex: 1 }]}>
              {e.msg}
            </Mono>
          </View>
        ))}
      </ScrollView>

      <TabBar active="log" />
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  header: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 16 },
  filters: { flexDirection: "row", gap: 8, marginTop: 14 },
  todayLabel: { paddingHorizontal: 20, paddingBottom: 8 },
  feed: {
    borderTopWidth: 1,
    paddingHorizontal: 20,
    paddingVertical: 16,
    flexGrow: 1,
  },
  logRow: { flexDirection: "row", gap: 10 },
  mono: { fontSize: 12.5, lineHeight: 26 },
  idCol: { width: 66 },
});
