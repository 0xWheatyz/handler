import React from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { fonts, radius, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { SegmentedControl } from "../components/SegmentedControl";
import { Card, Divider, Mono, SectionLabel } from "../components/primitives";
import { useAppState } from "../state/AppState";
import {
  clockTime,
  statusColor,
  statusLabel,
  statusTone,
  timeAgo,
} from "../api/format";

export function AgentDetailScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const {
    go,
    openAnswer,
    detailTab,
    setDetailTab,
    selectedAgent,
    selectedCheckmark,
    selectedLog,
    kill,
  } = useAppState();

  if (!selectedAgent) {
    return (
      <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
        <View style={{ height: insets.top }} />
        <View style={styles.content}>
          <PageHeader leading="back" onLeadingPress={() => go("fleet")} title="Agent" />
          <Text style={[text.body, { color: colors.textMuted }]}>
            This agent is no longer in the fleet.
          </Text>
        </View>
      </View>
    );
  }

  const agent = selectedAgent;
  const cm = selectedCheckmark;
  const openQuestion = cm?.open_question?.trim();

  const meta = [
    { label: "Started", value: timeAgo(agent.created_at) },
    { label: "Status", value: statusLabel(agent.status) },
    { label: "Tests", value: cm ? statusLabel(cm.tests_status) : "—" },
    { label: "Build", value: cm ? statusLabel(cm.build_status) : "—" },
  ];

  const logRows = [...selectedLog].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  function confirmKill() {
    Alert.alert(
      "Kill agent?",
      `Stop ${agent.name} and end its session. This can’t be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Kill",
          style: "destructive",
          onPress: () => {
            void kill(agent.project_id, agent.name).finally(() => go("fleet"));
          },
        },
      ],
    );
  }

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <ScrollView
        contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + 20 }]}
        showsVerticalScrollIndicator={false}
      >
        <PageHeader
          leading="back"
          onLeadingPress={() => go("fleet")}
          agentId={agent.name}
          badge={{ tone: statusTone(agent.status), label: statusLabel(agent.status) }}
        />

        <Text style={[text.h3, { color: colors.textHeading }]}>{agent.name}</Text>
        <Text style={[text.bodySm, { color: colors.textMuted, marginTop: 4, marginBottom: 16 }]}>
          {agent.project_id}
          {agent.role ? " · " : ""}
          {agent.role ? <Mono>{agent.role}</Mono> : null}
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
              {cm ? (
                <>
                  <SectionLabel style={{ marginBottom: 8 }}>Where it stopped</SectionLabel>
                  <Mono style={[styles.stateText, { color: colors.textBody }]}>
                    {cm.where_it_stopped?.trim() || "—"}
                  </Mono>

                  {cm.next_steps && cm.next_steps.length > 0 ? (
                    <>
                      <SectionLabel style={{ marginTop: 14, marginBottom: 8 }}>
                        Next steps
                      </SectionLabel>
                      {cm.next_steps.map((step, i) => (
                        <View key={i} style={styles.stepRow}>
                          <Text style={[styles.stateText, { color: colors.textMuted }]}>•  </Text>
                          <Text style={[styles.stateText, { color: colors.textBody, flex: 1 }]}>
                            {step}
                          </Text>
                        </View>
                      ))}
                    </>
                  ) : null}

                  {openQuestion ? (
                    <>
                      <SectionLabel style={{ marginTop: 14, marginBottom: 8, color: colors.warning }}>
                        Open question
                      </SectionLabel>
                      <Text
                        style={[
                          text.bodySm,
                          { color: colors.textBody, fontFamily: fonts.bodyItalic },
                        ]}
                      >
                        {openQuestion}
                      </Text>
                    </>
                  ) : null}

                  <Text style={[text.caption, { color: colors.textMuted, marginTop: 12 }]}>
                    updated {timeAgo(cm.checkpoint_at)}
                  </Text>
                </>
              ) : (
                <Text style={[text.bodySm, { color: colors.textMuted }]}>
                  No checkmark yet — this agent hasn’t reported a checkpoint.
                </Text>
              )}
            </View>

            <Card style={{ marginTop: 16 }}>
              {meta.map((m, i) => (
                <View key={m.label}>
                  {i > 0 && <Divider />}
                  <View style={styles.metaRow}>
                    <Text style={[text.bodySm, { color: colors.textMuted }]}>{m.label}</Text>
                    <Mono style={{ fontSize: 13, color: colors.textHeading }}>{m.value}</Mono>
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
            {logRows.length === 0 ? (
              <Text style={[text.bodySm, { color: colors.textMuted }]}>No log entries yet.</Text>
            ) : (
              logRows.map((row) => (
                <View key={row.id} style={styles.logRow}>
                  <Mono style={[styles.logMono, { color: colors.ink4 }]}>
                    {clockTime(row.created_at)}
                  </Mono>
                  <Mono style={[styles.logMono, { color: colors[statusColor(row.status)], flex: 1 }]}>
                    {row.summary?.trim() || statusLabel(row.status)}
                  </Mono>
                </View>
              ))
            )}
          </View>
        )}

        <View style={styles.actions}>
          {openQuestion ? (
            <Button
              size="lg"
              style={{ flex: 1 }}
              onPress={() => openAnswer(agent.project_id, agent.name)}
            >
              Answer
            </Button>
          ) : null}
          <Button size="lg" variant="danger" style={{ flex: 1 }} onPress={confirmKill}>
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
  stepRow: { flexDirection: "row" },
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
