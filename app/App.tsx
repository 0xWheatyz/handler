import React from "react";
import { View } from "react-native";
import { StatusBar } from "expo-status-bar";
import {
  SafeAreaProvider,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import {
  useFonts,
  Outfit_400Regular,
  Outfit_500Medium,
  Outfit_600SemiBold,
  Outfit_700Bold,
  Outfit_800ExtraBold,
} from "@expo-google-fonts/outfit";
import {
  Figtree_400Regular,
  Figtree_500Medium,
  Figtree_600SemiBold,
  Figtree_700Bold,
  Figtree_400Regular_Italic,
} from "@expo-google-fonts/figtree";
import {
  SplineSansMono_400Regular,
  SplineSansMono_500Medium,
  SplineSansMono_600SemiBold,
} from "@expo-google-fonts/spline-sans-mono";

import { useTheme } from "./src/theme/useTheme";
import { AppStateProvider, useAppState } from "./src/state/AppState";
import { FleetScreen } from "./src/screens/FleetScreen";
import { AgentDetailScreen } from "./src/screens/AgentDetailScreen";
import { AnswerScreen } from "./src/screens/AnswerScreen";
import { SpawnScreen } from "./src/screens/SpawnScreen";
import { LogScreen } from "./src/screens/LogScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";

function Router() {
  const { screen } = useAppState();
  const { scheme, colors } = useTheme();

  const Screen = {
    fleet: FleetScreen,
    detail: AgentDetailScreen,
    answer: AnswerScreen,
    spawn: SpawnScreen,
    log: LogScreen,
    settings: SettingsScreen,
  }[screen];

  return (
    <View style={{ flex: 1, backgroundColor: colors.surfacePage }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <Screen />
    </View>
  );
}

export default function App() {
  const [fontsLoaded] = useFonts({
    Outfit_400Regular,
    Outfit_500Medium,
    Outfit_600SemiBold,
    Outfit_700Bold,
    Outfit_800ExtraBold,
    Figtree_400Regular,
    Figtree_500Medium,
    Figtree_600SemiBold,
    Figtree_700Bold,
    Figtree_400Regular_Italic,
    SplineSansMono_400Regular,
    SplineSansMono_500Medium,
    SplineSansMono_600SemiBold,
  });

  return (
    <SafeAreaProvider>
      {fontsLoaded ? (
        <AppStateProvider>
          <Router />
        </AppStateProvider>
      ) : (
        <SplashPlaceholder />
      )}
    </SafeAreaProvider>
  );
}

/** Blank page-colored screen while fonts load (avoids a font flash). */
function SplashPlaceholder() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.surfacePage,
        paddingTop: insets.top,
      }}
    />
  );
}
