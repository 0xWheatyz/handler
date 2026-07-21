import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { fonts } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Badge } from "./Badge";
import { Icon } from "./Icon";
import { Mono } from "./primitives";
import type { BadgeTone } from "../state/AppState";

/**
 * Header for pushed screens (detail / answer / spawn): a leading nav control
 * plus either an agent id + status badge, or a plain title.
 */
export function PageHeader({
  leading,
  onLeadingPress,
  agentId,
  badge,
  title,
}: {
  leading: "back" | "close";
  onLeadingPress: () => void;
  agentId?: string;
  badge?: { tone: BadgeTone; label: string };
  title?: string;
}) {
  const { colors } = useTheme();
  return (
    <View style={styles.row}>
      <Pressable
        onPress={onLeadingPress}
        hitSlop={8}
        style={styles.control}
      >
        <Icon
          name={leading === "back" ? "chevronRight" : "x"}
          size={20}
          color={colors.textHeading}
          rotate={leading === "back" ? 180 : undefined}
        />
      </Pressable>
      {agentId ? (
        <Mono style={[styles.agentId, { color: colors.textMuted }]}>
          {agentId}
        </Mono>
      ) : (
        <Text style={[styles.title, { color: colors.textHeading }]}>
          {title}
        </Text>
      )}
      {badge ? <Badge tone={badge.tone}>{badge.label}</Badge> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 8,
    marginBottom: 16,
  },
  control: {
    width: 32,
    height: 32,
    marginLeft: -8,
    alignItems: "center",
    justifyContent: "center",
  },
  agentId: {
    flex: 1,
    fontSize: 13,
  },
  title: {
    flex: 1,
    fontFamily: fonts.bodySemiBold,
    fontSize: 13,
    lineHeight: 16,
  },
});
