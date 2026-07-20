import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { fonts, radius, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { SegmentedControl } from "../components/SegmentedControl";
import { Card, Divider, Mono, SectionLabel } from "../components/primitives";
import { useAppState } from "../state/AppState";
import { detailLog, detailMeta } from "../data/mock";

export function AgentDetailScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const {
    go,
    detailTab,
    setDetailTab,
    notAnswered,
    agentTone,
    agentStatus,
    agentStateText,
  } = useAppState();

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <ScrollView
        contentContainerStyle={[
          styles.content,
          { paddingBottom: insets.bottom + 20 },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <PageHeader
          leading="back"
          onLeadingPress={() => go("fleet")}
          agentId="agt-7a1d"
          badge={{ tone: agentTone, label: agentStatus }}
        />

        <Text style={[text.h3, { color: colors.textHeading }]}>
          Migrate agent state to sqlite
        </Text>
        <Text style={[text.bodySm, { color: colors.textMuted, marginTop: 4, marginBottom: 16 }]}>
          handler · branch <Mono>agt/7a1d</Mono>
        </Text>

        <View style={{ marginBottom: 16 }}>
          <SegmentedControl
            segments={[
              { value: "state", label: "Checkmark" },
              { value: "log", label: "Log" },
            ]}
            value={detailTab}
            onChange={setDetailTab}
          />
        </View>

        {detailTab === "state" ? (
          <>
            <View
              style={[
                styles.sunkenCard,
                { backgroundColor: colors.surfaceSunken, borderColor: colors.borderSubtle },
              ]}
            >
              <SectionLabel style={{ marginBottom: 8 }}>Current state</SectionLabel>
              <Mono style={[styles.stateText, { color: colors.textBody }]}>
                {agentStateText}
              </Mono>
              <Text style={[text.caption, { color: colors.textMuted, marginTop: 10 }]}>
                updated 2m ago
              </Text>
            </View>
            <Card style={{ marginTop: 16 }}>
              {detailMeta.map((m, i) => (
                <View key={m.label}>
                  {i > 0 && <Divider />}
                  <View style={styles.metaRow}>
                    <Text style={[text.bodySm, { color: colors.textMuted }]}>
                      {m.label}
                    </Text>
                    <Mono style={{ fontSize: 13, color: colors.textHeading }}>
                      {m.value}
                    </Mono>
                  </View>
                </View>
              ))}
            </Card>
          </>
        ) : (
          <View
            style={[
              styles.sunkenCard,
              { backgroundColor: colors.surfaceSunken, borderColor: colors.borderSubtle },
            ]}
          >
            {detailLog.map((row) => (
              <View key={row.t} style={styles.logRow}>
                <Mono style={[styles.logMono, { color: colors.ink4 }]}>
                  {row.t}
                </Mono>
                <Mono style={[styles.logMono, { color: colors[row.color] }]}>
                  {row.msg}
                </Mono>
              </View>
            ))}
          </View>
        )}

        <View style={styles.actions}>
          {notAnswered && (
            <Button size="lg" style={{ flex: 1 }} onPress={() => go("answer")}>
              Answer
            </Button>
          )}
          <Button size="lg" variant="secondary" style={{ flex: 1 }}>
            Pause
          </Button>
          <Button size="lg" variant="danger">
            Kill
          </Button>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  content: { paddingTop: 8, paddingHorizontal: 20 },
  sunkenCard: {
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 16,
  },
  stateText: {
    fontSize: 13,
    lineHeight: 22,
  },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  logRow: { flexDirection: "row", gap: 10 },
  logMono: {
    fontSize: 12.5,
    lineHeight: 26,
  },
  actions: {
    flexDirection: "row",
    gap: 10,
    marginTop: 20,
  },
});
