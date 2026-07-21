import React from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { fonts, radius } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";

/**
 * Leeworks Button, ported from components/forms/Button.jsx. Hover collapses
 * into press on touch; the primary/secondary/danger press tints are kept.
 */

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps {
  children: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  onPress?: () => void;
  style?: StyleProp<ViewStyle>;
}

const HEIGHT: Record<ButtonSize, number> = { sm: 32, md: 40, lg: 48 };
const PAD_X: Record<ButtonSize, number> = { sm: 12, md: 16, lg: 20 };
const FONT: Record<ButtonSize, number> = { sm: 13, md: 14, lg: 15 };

export function Button({
  children,
  variant = "primary",
  size = "md",
  onPress,
  style,
}: ButtonProps) {
  const { colors } = useTheme();

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => {
        const base: ViewStyle = {
          height: HEIGHT[size],
          paddingHorizontal: PAD_X[size],
          borderRadius: radius.md,
        };
        const byVariant: Record<ButtonVariant, ViewStyle> = {
          primary: {
            backgroundColor: pressed
              ? colors.interactivePress
              : colors.interactive,
          },
          secondary: {
            backgroundColor: pressed ? "rgba(20,20,19,0.05)" : colors.surfaceCard,
            borderWidth: 1,
            borderColor: colors.borderDefault,
          },
          ghost: {
            backgroundColor: pressed ? "rgba(20,20,19,0.05)" : "transparent",
          },
          danger: {
            backgroundColor: pressed ? "#8c2f25" : colors.danger,
          },
        };
        return [styles.base, base, byVariant[variant], style];
      }}
    >
      <View style={styles.inner}>
        <Text
          numberOfLines={1}
          style={[
            styles.label,
            {
              fontSize: FONT[size],
              color:
                variant === "primary"
                  ? colors.textInverse
                  : variant === "danger"
                    ? "#ffffff"
                    : variant === "secondary"
                      ? colors.textHeading
                      : colors.ink9,
            },
          ]}
        >
          {children}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    alignItems: "center",
    justifyContent: "center",
  },
  inner: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  label: {
    fontFamily: fonts.bodySemiBold,
  },
});
