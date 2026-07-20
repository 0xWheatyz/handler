import { useColorScheme } from "react-native";
import { darkColors, lightColors, type ThemeColors } from "./tokens";

export type Scheme = "light" | "dark";

/**
 * Resolves the active Leeworks palette from the OS appearance.
 *
 * The design exposed dark mode as a design-time prop (`data-theme`); on a
 * real iOS app the faithful equivalent is the system appearance, so the
 * theme follows `useColorScheme()` (app.json sets userInterfaceStyle
 * "automatic"). All six screens read colors through this hook.
 */
export function useTheme(): { colors: ThemeColors; scheme: Scheme } {
  const scheme: Scheme = useColorScheme() === "dark" ? "dark" : "light";
  return { colors: scheme === "dark" ? darkColors : lightColors, scheme };
}
