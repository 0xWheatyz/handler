import React, { useState } from "react";
import {
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
import { Chip } from "../components/Chip";
import { PageHeader } from "../components/PageHeader";
import { TextField } from "../components/TextField";
import { Mono, SectionLabel } from "../components/primitives";
import { useAppState } from "../state/AppState";
import { quickReplyLabels } from "../data/mock";

const QUESTION =
  "Migrations pass on the new sqlite store. Should I drop the legacy JSON store entirely, or keep it as a read-only fallback for one release?";

export function AnswerScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { go, quickPick, setQuickPick, sendResume } = useAppState();
  const [reply, setReply] = useState("");

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
            agentId="agt-7a1d"
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
            <SectionLabel style={{ marginBottom: 8 }}>Question · 2m ago</SectionLabel>
            <Mono style={[styles.questionText, { color: colors.textBody }]}>
              {QUESTION}
            </Mono>
          </View>

          <SectionLabel style={{ marginBottom: 10 }}>Quick replies</SectionLabel>
          <View style={styles.chips}>
            {quickReplyLabels.map((label, i) => (
              <Chip
                key={label}
                label={label}
                selected={quickPick === i}
                onPress={() => setQuickPick(i)}
              />
            ))}
          </View>

          <View style={styles.footer}>
            <TextField
              value={reply}
              onChangeText={setReply}
              placeholder="Or type a reply…"
            />
            <Button size="lg" style={{ width: "100%" }} onPress={sendResume}>
              Send & resume
            </Button>
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
    marginBottom: 20,
  },
  questionText: { fontSize: 13, lineHeight: 22 },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 20,
  },
  footer: { marginTop: "auto", gap: 12 },
});
