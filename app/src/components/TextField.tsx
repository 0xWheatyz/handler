import React, { useState } from "react";
import {
  StyleSheet,
  TextInput,
  View,
  type KeyboardTypeOptions,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from "react-native";
import { fonts, radius } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";

/**
 * Text field covering both the Leeworks single-line Input (answer reply) and
 * the multiline task textarea on the spawn screen. Focus swaps the border to
 * `--border-strong` per the Input component.
 */
export function TextField({
  value,
  onChangeText,
  placeholder,
  multiline = false,
  height = 48,
  style,
  secureTextEntry = false,
  autoCapitalize,
  autoCorrect,
  keyboardType,
}: {
  value: string;
  onChangeText: (t: string) => void;
  placeholder?: string;
  multiline?: boolean;
  /** For single-line this is the control height; for multiline, the box height. */
  height?: number;
  style?: StyleProp<ViewStyle>;
  secureTextEntry?: boolean;
  autoCapitalize?: TextInputProps["autoCapitalize"];
  autoCorrect?: boolean;
  keyboardType?: KeyboardTypeOptions;
}) {
  const { colors } = useTheme();
  const [focus, setFocus] = useState(false);
  return (
    <View
      style={[
        styles.wrap,
        {
          height,
          backgroundColor: colors.surfaceCard,
          borderColor: focus ? colors.borderStrong : colors.borderDefault,
          alignItems: multiline ? "stretch" : "center",
          paddingVertical: multiline ? 12 : 0,
        },
        style,
      ]}
    >
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textMuted}
        multiline={multiline}
        secureTextEntry={secureTextEntry}
        autoCapitalize={autoCapitalize}
        autoCorrect={autoCorrect}
        keyboardType={keyboardType}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        style={[
          styles.input,
          {
            color: colors.textHeading,
            textAlignVertical: multiline ? "top" : "center",
          },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 14,
  },
  input: {
    flex: 1,
    alignSelf: "stretch",
    fontFamily: fonts.bodyRegular,
    fontSize: 15,
    padding: 0,
  },
});
