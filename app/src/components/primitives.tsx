import React from "react";
import {
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";
import { fonts, radius, shadows, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";

/** White card: 1px subtle border, 10px radius, whisper-quiet shadow. */
export function Card({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useTheme();
  return (
    <View
      style={[
        {
          backgroundColor: colors.surfaceCard,
          borderWidth: 1,
          borderColor: colors.borderSubtle,
          borderRadius: radius.lg,
        },
        shadows.card,
        style,
      ]}
    >
      {children}
    </View>
  );
}

/** Uppercase, letter-spaced overline label (Outfit 600, 11px). */
export function SectionLabel({
  children,
  style,
}: {
  children: string;
  style?: StyleProp<TextStyle>;
}) {
  const { colors } = useTheme();
  return (
    <Text style={[text.overline, { color: colors.textMuted }, style]}>
      {children}
    </Text>
  );
}

/** Hairline divider used between card rows. */
export function Divider() {
  const { colors } = useTheme();
  return <View style={{ height: 1, backgroundColor: colors.borderSubtle }} />;
}

/** 8px status dot. */
export function StatusDot({ color, size = 8 }: { color: string; size?: number }) {
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: color,
      }}
    />
  );
}

/** Monospace text helper (Spline Sans Mono). */
export function Mono({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: StyleProp<TextStyle>;
}) {
  return <Text style={[monoStyles.mono, style]}>{children}</Text>;
}

const monoStyles = StyleSheet.create({
  mono: { fontFamily: fonts.monoRegular },
});
