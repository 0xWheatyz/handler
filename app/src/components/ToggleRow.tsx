import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Switch } from "./Switch";

/**
 * A labelled settings row with a trailing Switch — used for the spawn options
 * and the notification settings. Matches the `min-height:44px` tap target.
 */
export function ToggleRow({
  title,
  subtitle,
  value,
  onValueChange,
}: {
  title: string;
  subtitle: string;
  value: boolean;
  onValueChange: (v: boolean) => void;
}) {
  const { colors } = useTheme();
  return (
    <View style={styles.row}>
      <View style={{ flex: 1, paddingRight: 12 }}>
        <Text style={[text.label, { color: colors.textHeading }]}>{title}</Text>
        <Text style={[text.caption, { color: colors.textMuted, marginTop: 2 }]}>
          {subtitle}
        </Text>
      </View>
      <Switch value={value} onValueChange={onValueChange} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 16,
    minHeight: 44,
  },
});
