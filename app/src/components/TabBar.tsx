import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { fonts } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Icon, type IconName } from "./Icon";
import { useAppState, type Screen } from "../state/AppState";

/**
 * Bottom tab bar shown on the three primary screens (Fleet / Log / Settings).
 * The design's fixed 24px bottom inset is replaced by the real home-indicator
 * safe-area inset.
 */

const TABS: { key: Screen; label: string; icon: IconName }[] = [
  { key: "fleet", label: "Fleet", icon: "home" },
  { key: "log", label: "Log", icon: "file" },
  { key: "settings", label: "Settings", icon: "settings" },
];

export function TabBar({ active }: { active: Screen }) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { go } = useAppState();

  return (
    <View
      style={[
        styles.bar,
        {
          backgroundColor: colors.surfacePage,
          borderTopColor: colors.borderSubtle,
          paddingBottom: Math.max(insets.bottom, 12),
        },
      ]}
    >
      {TABS.map((t) => {
        const on = t.key === active;
        const tint = on ? colors.textHeading : colors.ink4;
        return (
          <Pressable
            key={t.key}
            style={styles.tab}
            onPress={() => go(t.key)}
          >
            <Icon
              name={t.icon}
              size={22}
              color={tint}
              strokeWidth={on ? 2 : 1.75}
            />
            <Text
              style={[
                styles.label,
                {
                  color: tint,
                  fontFamily: on ? fonts.bodySemiBold : fonts.bodyMedium,
                },
              ]}
            >
              {t.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    borderTopWidth: 1,
    paddingTop: 8,
    paddingHorizontal: 12,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    gap: 4,
    paddingVertical: 6,
  },
  label: {
    fontSize: 12,
    lineHeight: 14,
  },
});
