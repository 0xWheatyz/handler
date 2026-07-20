import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { fonts, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import {
  Card,
  Divider,
  Mono,
  SectionLabel,
  StatusDot,
} from "../components/primitives";
import { TabBar } from "../components/TabBar";
import { useAppState } from "../state/AppState";
import {
  recentCheckmarks,
  waitingAgents,
  type Checkmark,
  type WaitingAgent,
} from "../data/mock";

export function FleetScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { go, notAnswered } = useAppState();

  const waiting = waitingAgents.filter((a) => !(a.clearsOnAnswer && !notAnswered));

  const stats = [
    { label: "Running", value: "6", tint: colors.textHeading },
    { label: "Waiting", value: "3", tint: colors.warning },
    { label: "Done", value: "42", tint: colors.textHeading },
  ];

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={[text.h3, { color: colors.textHeading }]}>Fleet</Text>
            <Text style={[text.bodySm, { color: colors.textMuted, marginTop: 2 }]}>
              12 agents · 3 waiting on you
            </Text>
          </View>
          <Button size="sm" onPress={() => go("spawn")}>
            New
          </Button>
        </View>

        <View style={styles.statsRow}>
          {stats.map((s) => (
            <Card key={s.label} style={styles.statCard}>
              <Text style={[text.caption, { color: colors.textMuted }]}>
                {s.label}
              </Text>
              <Text style={[styles.statValue, { color: s.tint }]}>
                {s.value}
              </Text>
            </Card>
          ))}
        </View>

        <SectionLabel style={styles.overline}>Waiting on you</SectionLabel>
        <Card style={styles.section}>
          {waiting.map((a, i) => (
            <View key={a.id}>
              {i > 0 && <Divider />}
              <WaitingRow agent={a} onAnswer={() => go("answer")} />
            </View>
          ))}
        </Card>

        <SectionLabel style={styles.overline}>Recent checkmarks</SectionLabel>
        <Card>
          {recentCheckmarks.map((c, i) => (
            <View key={c.title}>
              {i > 0 && <Divider />}
              <CheckmarkRow checkmark={c} onPress={() => go("detail")} />
            </View>
          ))}
        </Card>
      </ScrollView>
      <TabBar active="fleet" />
    </View>
  );
}

function WaitingRow({
  agent,
  onAnswer,
}: {
  agent: WaitingAgent;
  onAnswer: () => void;
}) {
  const { colors } = useTheme();
  return (
    <View style={styles.rowPad}>
      <View style={styles.waitingTop}>
        <Mono style={{ fontSize: 12, color: colors.textMuted }}>{agent.id}</Mono>
        <Text
          numberOfLines={1}
          style={[styles.rowTitle, { color: colors.textHeading, flex: 1 }]}
        >
          {agent.title}
        </Text>
      </View>
      <View style={styles.waitingBottom}>
        <Text
          style={[
            text.bodySm,
            { color: colors.textBody, flex: 1, fontFamily: fonts.bodyItalic },
          ]}
        >
          {agent.question}
        </Text>
        <Button size="sm" variant="secondary" onPress={onAnswer}>
          Answer
        </Button>
      </View>
    </View>
  );
}

function CheckmarkRow({
  checkmark,
  onPress,
}: {
  checkmark: Checkmark;
  onPress: () => void;
}) {
  const { colors } = useTheme();
  const dot = checkmark.status === "positive" ? colors.positive : colors.danger;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.checkmarkRow,
        pressed && { backgroundColor: colors.surfaceSunken },
      ]}
    >
      <StatusDot color={dot} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text
          numberOfLines={1}
          style={[styles.rowTitle, { color: colors.textHeading }]}
        >
          {checkmark.title}
        </Text>
        <Text style={[text.caption, { color: colors.textMuted, marginTop: 2 }]}>
          {checkmark.meta}
        </Text>
      </View>
      <Icon name="chevronRight" size={16} color={colors.ink4} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  content: { paddingTop: 8, paddingHorizontal: 20, paddingBottom: 20 },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginTop: 12,
    marginBottom: 20,
  },
  statsRow: { flexDirection: "row", gap: 12, marginBottom: 20 },
  statCard: { flex: 1, paddingVertical: 14, paddingHorizontal: 16 },
  statValue: {
    fontFamily: fonts.monoSemiBold,
    fontSize: 24,
    lineHeight: 28,
    marginTop: 4,
  },
  overline: { marginBottom: 10 },
  section: { marginBottom: 20 },
  rowPad: { paddingVertical: 14, paddingHorizontal: 16 },
  waitingTop: { flexDirection: "row", alignItems: "center", gap: 8 },
  waitingBottom: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginTop: 8,
  },
  rowTitle: {
    fontFamily: fonts.bodySemiBold,
    fontSize: 13,
    lineHeight: 16,
  },
  checkmarkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    minHeight: 44,
  },
});
