import type { TextStyle, ViewStyle } from "react-native";

/**
 * Leeworks design tokens, ported from the CSS token files in
 * project/_ds/.../tokens/*.css to typed React Native values.
 *
 * CSS `font:` shorthand and weight-by-number don't exist in RN, so each
 * weight maps to a concretely-loaded font family (see `fonts`), and the
 * composite `--type-*` styles become the `text` style objects below.
 */

// ---- Fonts (families loaded via @expo-google-fonts) --------------------
export const fonts = {
  displayRegular: "Outfit_400Regular",
  displayMedium: "Outfit_500Medium",
  displaySemiBold: "Outfit_600SemiBold",
  displayBold: "Outfit_700Bold",
  displayExtraBold: "Outfit_800ExtraBold",

  bodyRegular: "Figtree_400Regular",
  bodyMedium: "Figtree_500Medium",
  bodySemiBold: "Figtree_600SemiBold",
  bodyBold: "Figtree_700Bold",
  bodyItalic: "Figtree_400Regular_Italic",

  monoRegular: "SplineSansMono_400Regular",
  monoMedium: "SplineSansMono_500Medium",
  monoSemiBold: "SplineSansMono_600SemiBold",
} as const;

// ---- Radii (effects.css) -----------------------------------------------
export const radius = {
  sm: 6,
  md: 8,
  lg: 10,
  xl: 16,
  pill: 999,
} as const;

// ---- Color palettes (colors.css) ---------------------------------------
// The warm-neutral ink ramp is shared across themes; only the semantic
// aliases and status colors flip between light and dark.
const ink = {
  white: "#ffffff",
  ink0: "#fcfcfb",
  ink1: "#f6f6f4",
  ink2: "#ececea",
  ink3: "#dcdcd8",
  ink4: "#b8b8b3",
  ink5: "#8b8b86",
  ink6: "#62625e",
  ink7: "#3d3d3a",
  ink8: "#232321",
  ink9: "#141413",
} as const;

export const lightColors = {
  ...ink,

  signal: "#1d6b45",
  signalTint: "#e8f2ec",
  positive: "#1d6b45",
  positiveTint: "#e8f2ec",
  warning: "#8a6116",
  warningTint: "#f7efdd",
  danger: "#a33a2f",
  dangerTint: "#f9e9e6",

  surfacePage: ink.white,
  surfaceRaised: ink.white,
  surfaceSunken: ink.ink1,
  surfaceCard: ink.white,
  surfaceInverse: ink.ink9,

  textHeading: ink.ink9,
  textBody: ink.ink7,
  textMuted: ink.ink5,
  textInverse: ink.ink0,

  borderSubtle: ink.ink2,
  borderDefault: ink.ink3,
  borderStrong: ink.ink9,

  interactive: ink.ink9,
  interactiveHover: ink.ink7,
  interactivePress: "#000000",
} as const;

export type ThemeColors = Record<keyof typeof lightColors, string>;

export const darkColors: ThemeColors = {
  ...ink,

  signal: "#4fa377",
  signalTint: "#1d2f26",
  positive: "#4fa377",
  positiveTint: "#1d2f26",
  warning: "#c99a3f",
  warningTint: "#2f2818",
  danger: "#d0685c",
  dangerTint: "#331e1b",

  surfacePage: "#161615",
  surfaceRaised: "#1e1e1d",
  surfaceSunken: "#111110",
  surfaceCard: "#1e1e1d",
  surfaceInverse: ink.ink0,

  textHeading: "#f4f4f2",
  textBody: "#c9c9c4",
  textMuted: "#8b8b86",
  textInverse: ink.ink9,

  borderSubtle: "#2b2b29",
  borderDefault: "#3a3a37",
  borderStrong: "#f4f4f2",

  interactive: "#f4f4f2",
  interactiveHover: "#d8d8d4",
  interactivePress: "#ffffff",
};

// ---- Composite text styles (typography.css `--type-*`) -----------------
// Color is intentionally omitted — callers set it from the active palette.
export const text = {
  // `--type-h3` + font-display + tracking-tight, as the screens use it.
  h3: {
    fontFamily: fonts.displaySemiBold,
    fontSize: 24,
    lineHeight: 31,
    letterSpacing: -0.48,
  } as TextStyle,
  body: {
    fontFamily: fonts.bodyRegular,
    fontSize: 15,
    lineHeight: 23,
  } as TextStyle,
  bodySm: {
    fontFamily: fonts.bodyRegular,
    fontSize: 13,
    lineHeight: 20,
  } as TextStyle,
  label: {
    fontFamily: fonts.bodySemiBold,
    fontSize: 13,
    lineHeight: 16,
  } as TextStyle,
  caption: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    lineHeight: 17,
  } as TextStyle,
  // Overlines are rendered at 11px with wide tracking + uppercase.
  overline: {
    fontFamily: fonts.displaySemiBold,
    fontSize: 11,
    lineHeight: 13,
    letterSpacing: 0.88,
    textTransform: "uppercase",
  } as TextStyle,
} as const;

// ---- Shadows (effects.css) ---------------------------------------------
export const shadows = {
  card: {
    shadowColor: "#141413",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  } as ViewStyle,
  raised: {
    shadowColor: "#141413",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 8,
    elevation: 3,
  } as ViewStyle,
} as const;
