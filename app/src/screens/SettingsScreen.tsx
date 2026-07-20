import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Button } from "../components/Button";
import { ToggleRow } from "../components/ToggleRow";
import {
  Card,
  Divider,
  Mono,
  SectionLabel,
  StatusDot,
} from "../components/primitives";
import { TabBar } from "../components/TabBar";
import { useAppState } from "../state/AppState";

export function SettingsScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { swPushWait, setSwPushWait, swPushFail, setSwPushFail } = useAppState();

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={[text.h3, { color: colors.textHeading, marginVertical: 12, marginBottom: 20 }]}>
          Settings
        </Text>

        <SectionLabel style={{ marginBottom: 10 }}>Server</SectionLabel>
        <Card style={{ marginBottom: 20 }}>
          <InfoRow label="Endpoint" value="https://handler.wheaty.dev" />
          <Divider />
          <InfoRow label="API key" value="hnd_••••••••4f2a" />
          <Divider />
          <View style={styles.infoRow}>
            <Text style={[text.label, { color: colors.textHeading }]}>Status</Text>
            <View style={styles.statusValue}>
              <StatusDot color={colors.positive} size={7} />
              <Mono style={[styles.valueMono, { color: colors.positive }]}>
                connected · 38ms
              </Mono>
            </View>
          </View>
        </Card>

        <SectionLabel style={{ marginBottom: 10 }}>Notifications</SectionLabel>
        <Card style={{ marginBottom: 20 }}>
          <ToggleRow
            title="Waiting on input"
            subtitle="Push when an agent pauses"
            value={swPushWait}
            onValueChange={setSwPushWait}
          />
          <Divider />
          <ToggleRow
            title="Failures"
            subtitle="Push when a checkmark fails"
            value={swPushFail}
            onValueChange={setSwPushFail}
          />
        </Card>

        <Button variant="secondary" size="lg" style={{ width: "100%" }}>
          Sign out
        </Button>
      </ScrollView>
      <TabBar active="settings" />
    </View>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  const { colors } = useTheme();
  return (
    <View style={styles.infoRow}>
      <Text style={[text.label, { color: colors.textHeading }]}>{label}</Text>
      <Mono style={[styles.valueMono, { color: colors.textMuted }]}>{value}</Mono>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  content: { paddingTop: 8, paddingHorizontal: 20, paddingBottom: 20 },
  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 16,
    minHeight: 44,
    gap: 12,
  },
  statusValue: { flexDirection: "row", alignItems: "center", gap: 6 },
  valueMono: { fontSize: 12.5 },
});
