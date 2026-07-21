import React from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
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
import {
  useAppState,
  type RecentItem,
  type WaitingItem,
} from "../state/AppState";

export function FleetScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { go, openAnswer, openDetail, waiting, recent, counts, loading, error, refresh } =
    useAppState();

  const empty = waiting.length === 0 && recent.length === 0;

  const stats = [
    { label: "Running", value: counts.running, tint: colors.textHeading },
    { label: "Waiting", value: counts.waiting, tint: colors.warning },
    { label: "Done", value: counts.done, tint: colors.textHeading },
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
              {counts.running} running · {counts.waiting} waiting on you
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

        {loading && empty && !error ? (
          <View style={styles.centered}>
            <ActivityIndicator color={colors.textMuted} />
          </View>
        ) : error && empty ? (
          <Card style={styles.errorCard}>
            <SectionLabel style={{ marginBottom: 6 }}>Couldn’t load fleet</SectionLabel>
            <Text style={[text.bodySm, { color: colors.textBody, marginBottom: 14 }]}>
              {error}
            </Text>
            <Button size="md" variant="secondary" onPress={() => refresh()}>
              Retry
            </Button>
          </Card>
        ) : (
          <>
            <SectionLabel style={styles.overline}>Waiting on you</SectionLabel>
            <Card style={styles.section}>
              {waiting.length === 0 ? (
                <View style={styles.rowPad}>
                  <Text style={[text.bodySm, { color: colors.textMuted }]}>
                    Nothing waiting on you.
                  </Text>
                </View>
              ) : (
                waiting.map((a, i) => (
                  <View key={`${a.project}/${a.name}`}>
                    {i > 0 && <Divider />}
                    <WaitingRow
                      agent={a}
                      onAnswer={() => openAnswer(a.project, a.name)}
                    />
                  </View>
                ))
              )}
            </Card>

            <SectionLabel style={styles.overline}>Recent checkmarks</SectionLabel>
            <Card>
              {recent.length === 0 ? (
                <View style={styles.rowPad}>
                  <Text style={[text.bodySm, { color: colors.textMuted }]}>
                    No checkmarks yet.
                  </Text>
                </View>
              ) : (
                recent.map((c, i) => (
                  <View key={c.key}>
                    {i > 0 && <Divider />}
                    <CheckmarkRow
                      checkmark={c}
                      onPress={() => openDetail(c.project, c.name)}
                    />
                  </View>
                ))
              )}
            </Card>
          </>
        )}
      </ScrollView>
      <TabBar active="fleet" />
    </View>
  );
}

function WaitingRow({
  agent,
  onAnswer,
}: {
  agent: WaitingItem;
  onAnswer: () => void;
}) {
  const { colors } = useTheme();
  return (
    <View style={styles.rowPad}>
      <View style={styles.waitingTop}>
        <Mono style={{ fontSize: 12, color: colors.textMuted }}>{agent.name}</Mono>
        <Text
          numberOfLines={1}
          style={[styles.rowTitle, { color: colors.textHeading, flex: 1 }]}
        >
          {agent.project}
        </Text>
      </View>
      <View style={styles.waitingBottom}>
        <Text
          numberOfLines={2}
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
  checkmark: RecentItem;
  onPress: () => void;
}) {
  const { colors } = useTheme();
  const dot = checkmark.tone === "positive" ? colors.positive : colors.danger;
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
  centered: { paddingVertical: 48, alignItems: "center", justifyContent: "center" },
  errorCard: { padding: 16, alignItems: "flex-start" },
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
