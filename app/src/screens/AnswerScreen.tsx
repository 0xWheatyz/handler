import React, { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { radius, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { TextField } from "../components/TextField";
import { Mono, SectionLabel } from "../components/primitives";
import { useAppState } from "../state/AppState";
import { timeAgo } from "../api/format";

export function AnswerScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { go, selectedAgent, selectedCheckmark, sendAnswer } = useAppState();
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  if (!selectedAgent) {
    return (
      <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
        <View style={{ height: insets.top }} />
        <View style={styles.content}>
          <PageHeader leading="back" onLeadingPress={() => go("fleet")} title="Answer" />
          <Text style={[text.body, { color: colors.textMuted }]}>
            This agent is no longer in the fleet.
          </Text>
        </View>
      </View>
    );
  }

  const agent = selectedAgent;
  const question =
    selectedCheckmark?.open_question?.trim() ||
    "This agent is paused and waiting for input.";
  const askedAt = selectedCheckmark?.checkpoint_at;

  async function send() {
    if (!reply.trim()) {
      setError("Enter a reply.");
      return;
    }
    setError(null);
    setNote(null);
    setBusy(true);
    try {
      const res = await sendAnswer(reply.trim());
      if (res.resumed) {
        go("detail");
      } else {
        setNote(res.note ?? "Answer saved.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t send answer.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={[styles.content, { paddingBottom: insets.bottom + 20 }]}>
          <PageHeader
            leading="back"
            onLeadingPress={() => go("detail")}
            agentId={agent.name}
            badge={{ tone: "warning", label: "Waiting" }}
          />

          <Text style={[text.h3, { color: colors.textHeading, marginBottom: 16 }]}>
            Agent needs input
          </Text>

          <View
            style={[
              styles.questionCard,
              { backgroundColor: colors.surfaceSunken, borderColor: colors.borderSubtle },
            ]}
          >
            <SectionLabel style={{ marginBottom: 8 }}>
              {`Question${askedAt ? ` · ${timeAgo(askedAt)} ago` : ""}`}
            </SectionLabel>
            <Mono style={[styles.questionText, { color: colors.textBody }]}>
              {question}
            </Mono>
          </View>

          {error ? (
            <View
              style={[
                styles.notice,
                { backgroundColor: colors.dangerTint, borderColor: colors.danger },
              ]}
            >
              <Text style={[text.bodySm, { color: colors.danger }]}>{error}</Text>
            </View>
          ) : null}
          {note ? (
            <View
              style={[
                styles.notice,
                { backgroundColor: colors.warningTint, borderColor: colors.warning },
              ]}
            >
              <Text style={[text.bodySm, { color: colors.warning }]}>{note}</Text>
            </View>
          ) : null}

          <View style={styles.footer}>
            <TextField
              value={reply}
              onChangeText={setReply}
              placeholder="Type a reply…"
              multiline
              height={100}
            />
            <Button
              size="lg"
              style={{ width: "100%" }}
              onPress={busy ? undefined : send}
            >
              {busy ? "Sending…" : "Send & resume"}
            </Button>
            {busy ? (
              <ActivityIndicator color={colors.textMuted} style={{ marginTop: 4 }} />
            ) : null}
          </View>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  flex: { flex: 1 },
  content: { flex: 1, paddingTop: 8, paddingHorizontal: 20 },
  questionCard: {
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 16,
    marginBottom: 16,
  },
  questionText: { fontSize: 13, lineHeight: 22 },
  notice: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
    marginBottom: 12,
  },
  footer: { marginTop: "auto", gap: 12 },
});
