import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { fonts, radius } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import type { BadgeTone } from "../state/AppState";

/** Leeworks Badge, ported from components/display/Badge.jsx. */
export function Badge({ tone, children }: { tone: BadgeTone; children: string }) {
  const { colors } = useTheme();
  const tones: Record<BadgeTone, { bg: string; fg: string }> = {
    neutral: { bg: colors.ink1, fg: colors.ink7 },
    positive: { bg: colors.positiveTint, fg: colors.positive },
    warning: { bg: colors.warningTint, fg: colors.warning },
    danger: { bg: colors.dangerTint, fg: colors.danger },
  };
  const t = tones[tone];
  return (
    <View style={[styles.badge, { backgroundColor: t.bg }]}>
      <Text style={[styles.text, { color: t.fg }]}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    paddingVertical: 3,
    paddingHorizontal: 10,
    borderRadius: radius.pill,
  },
  text: {
    fontFamily: fonts.bodySemiBold,
    fontSize: 12,
    lineHeight: 17,
  },
});
