import React, { useEffect, useMemo, useState } from "react";
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
import { useServerConfig } from "../state/ServerConfig";
import { createClient } from "../api/client";

type Ping =
  | { state: "checking" }
  | { state: "ok"; latencyMs: number }
  | { state: "error" };

export function SettingsScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { config, clear } = useServerConfig();

  // Notification toggles stay local (no server-side counterpart yet).
  const [pushWait, setPushWait] = useState(true);
  const [pushFail, setPushFail] = useState(true);

  const [ping, setPing] = useState<Ping>({ state: "checking" });

  const client = useMemo(
    () => (config ? createClient(config.endpoint, config.token, () => {}) : null),
    [config],
  );

  useEffect(() => {
    if (!client) return;
    let active = true;
    setPing({ state: "checking" });
    const started = Date.now();
    client
      .api<{ status: string }>("/health")
      .then(() => {
        if (active) setPing({ state: "ok", latencyMs: Date.now() - started });
      })
      .catch(() => {
        if (active) setPing({ state: "error" });
      });
    return () => {
      active = false;
    };
  }, [client]);

  const maskedToken = config
    ? `••••••••${config.token.slice(-4)}`
    : "—";

  const status =
    ping.state === "ok"
      ? { color: colors.positive, label: `connected · ${ping.latencyMs}ms` }
      : ping.state === "error"
        ? { color: colors.danger, label: "unreachable" }
        : { color: colors.textMuted, label: "checking…" };

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
          <InfoRow label="Endpoint" value={config?.endpoint ?? "—"} />
          <Divider />
          <InfoRow label="API token" value={maskedToken} />
          <Divider />
          <View style={styles.infoRow}>
            <Text style={[text.label, { color: colors.textHeading }]}>Status</Text>
            <View style={styles.statusValue}>
              <StatusDot color={status.color} size={7} />
              <Mono style={[styles.valueMono, { color: status.color }]}>
                {status.label}
              </Mono>
            </View>
          </View>
        </Card>

        <SectionLabel style={{ marginBottom: 10 }}>Notifications</SectionLabel>
        <Card style={{ marginBottom: 20 }}>
          <ToggleRow
            title="Waiting on input"
            subtitle="Push when an agent pauses"
            value={pushWait}
            onValueChange={setPushWait}
          />
          <Divider />
          <ToggleRow
            title="Failures"
            subtitle="Push when a checkmark fails"
            value={pushFail}
            onValueChange={setPushFail}
          />
        </Card>

        <Button
          variant="secondary"
          size="lg"
          style={{ width: "100%" }}
          onPress={() => void clear()}
        >
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
      <Mono
        numberOfLines={1}
        style={[styles.valueMono, styles.valueFlex, { color: colors.textMuted }]}
      >
        {value}
      </Mono>
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
  valueFlex: { flex: 1, textAlign: "right" },
});
