import React from "react";
import { Pressable, StyleSheet, Text } from "react-native";
import { fonts, radius } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";

/**
 * Pill chip used for both the answer quick-replies and the log filters.
 * Ported from the `chip()` style helper in the DC script.
 */
export function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.chip,
        {
          backgroundColor: selected ? colors.interactive : colors.surfacePage,
          borderColor: selected ? colors.borderStrong : colors.borderDefault,
        },
      ]}
    >
      <Text
        style={[
          styles.label,
          { color: selected ? "#ffffff" : colors.textBody },
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  label: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    lineHeight: 13,
  },
});
