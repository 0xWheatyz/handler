import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { fonts, radius, shadows } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";

/**
 * Segmented control (the Checkmark / Log toggle on agent detail).
 * Ported from the `seg()` style helper in the DC script.
 */
export function SegmentedControl<T extends string>({
  segments,
  value,
  onChange,
}: {
  segments: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  const { colors } = useTheme();
  return (
    <View style={[styles.track, { backgroundColor: colors.surfaceSunken }]}>
      {segments.map((s) => {
        const on = s.value === value;
        return (
          <Pressable
            key={s.value}
            onPress={() => onChange(s.value)}
            style={[
              styles.segment,
              on && {
                backgroundColor: colors.surfacePage,
                ...shadows.card,
              },
            ]}
          >
            <Text
              style={[
                styles.label,
                { color: on ? colors.textHeading : colors.textMuted },
              ]}
            >
              {s.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: "row",
    borderRadius: radius.md,
    padding: 3,
  },
  segment: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  label: {
    fontFamily: fonts.bodySemiBold,
    fontSize: 13,
    lineHeight: 13,
  },
});
