import React, { useState } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { fonts, radius, shadows, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Icon } from "./Icon";

/**
 * Leeworks Select, ported from components/forms/Select.jsx. Native <select>
 * has no cross-platform styling in RN, so the field opens a bottom sheet of
 * options — same visual field (value + chevron), real picking behavior.
 */
export function Select({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  const { colors } = useTheme();
  const [open, setOpen] = useState(false);

  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.label, { color: colors.textHeading }]}>{label}</Text>
      <Pressable
        onPress={() => setOpen(true)}
        style={[
          styles.field,
          { backgroundColor: colors.surfaceCard, borderColor: colors.borderDefault },
        ]}
      >
        <Text style={[text.body, { color: colors.textHeading, flex: 1 }]}>
          {value}
        </Text>
        <Icon name="chevronDown" size={16} color={colors.textMuted} />
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable
            style={[
              styles.sheet,
              { backgroundColor: colors.surfaceCard, borderColor: colors.borderSubtle },
              shadows.raised,
            ]}
          >
            {options.map((opt) => {
              const on = opt === value;
              return (
                <Pressable
                  key={opt}
                  onPress={() => {
                    onChange(opt);
                    setOpen(false);
                  }}
                  style={({ pressed }) => [
                    styles.option,
                    pressed && { backgroundColor: colors.surfaceSunken },
                  ]}
                >
                  <Text
                    style={[
                      text.body,
                      {
                        color: colors.textHeading,
                        fontFamily: on ? fonts.bodySemiBold : fonts.bodyRegular,
                        flex: 1,
                      },
                    ]}
                  >
                    {opt}
                  </Text>
                  {on && <Icon name="chevronRight" size={16} color={colors.textMuted} />}
                </Pressable>
              );
            })}
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  label: {
    fontFamily: fonts.bodySemiBold,
    fontSize: 13,
    lineHeight: 16,
  },
  field: {
    height: 48,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 12,
    gap: 8,
  },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(20,20,19,0.4)",
    justifyContent: "flex-end",
    padding: 20,
  },
  sheet: {
    borderWidth: 1,
    borderRadius: radius.xl,
    overflow: "hidden",
    marginBottom: 24,
  },
  option: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 16,
    paddingHorizontal: 20,
    minHeight: 44,
  },
});
