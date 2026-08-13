import React from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { radius, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { PageHeader } from "./PageHeader";
import { useAppState, type Screen } from "../state/AppState";

/**
 * Page chrome shared by every management subscreen (Settings → Manage → …):
 * safe-area top, back header, title/subtitle, keyboard-aware scroll body.
 */
export function ManageShell({
  title,
  subtitle,
  backTo = "manage",
  children,
}: {
  title: string;
  subtitle?: string;
  backTo?: Screen;
  children: React.ReactNode;
}) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { go } = useAppState();

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          style={styles.flex}
          contentContainerStyle={[
            styles.content,
            { paddingBottom: insets.bottom + 24 },
          ]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <PageHeader leading="back" onLeadingPress={() => go(backTo)} title={title} />
          {subtitle ? (
            <Text style={[text.bodySm, { color: colors.textMuted, marginBottom: 16 }]}>
              {subtitle}
            </Text>
          ) : null}
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

/** Inline danger notice used by the manage screens for mutation errors. */
export function ErrorNotice({ message }: { message: string | null }) {
  const { colors } = useTheme();
  if (!message) return null;
  return (
    <View
      style={[
        styles.notice,
        { backgroundColor: colors.dangerTint, borderColor: colors.danger },
      ]}
    >
      <Text style={[text.bodySm, { color: colors.danger }]}>{message}</Text>
    </View>
  );
}

/** Labelled block wrapping a TextField (the manage forms' field-with-label pattern). */
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  const { colors } = useTheme();
  return (
    <View>
      <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
        {label}
      </Text>
      {children}
      {hint ? (
        <Text style={[text.caption, { color: colors.textMuted, marginTop: 6 }]}>
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  flex: { flex: 1 },
  content: { paddingTop: 8, paddingHorizontal: 20 },
  notice: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
    marginBottom: 16,
  },
});
