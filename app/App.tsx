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
import {
  AppStateProvider,
  useAppState,
  type Screen as ScreenName,
} from "./src/state/AppState";
import { ManageScreen } from "./src/screens/manage/ManageScreen";
import { ModelsScreen } from "./src/screens/manage/ModelsScreen";
import { SkillsScreen } from "./src/screens/manage/SkillsScreen";
import { ConnectorsScreen } from "./src/screens/manage/ConnectorsScreen";
import { PluginsScreen } from "./src/screens/manage/PluginsScreen";
import { PermissionsScreen } from "./src/screens/manage/PermissionsScreen";
import { RepositoriesScreen } from "./src/screens/manage/RepositoriesScreen";
import { GitServersScreen } from "./src/screens/manage/GitServersScreen";
import { ApprovalsScreen } from "./src/screens/manage/ApprovalsScreen";
import { ActivityScreen } from "./src/screens/manage/ActivityScreen";
import { SharedContextScreen } from "./src/screens/manage/SharedContextScreen";
import { UsersScreen } from "./src/screens/manage/UsersScreen";
import { AccountScreen } from "./src/screens/manage/AccountScreen";
import { ClaudeLoginScreen } from "./src/screens/manage/ClaudeLoginScreen";
import { ServerConfigProvider, useServerConfig } from "./src/state/ServerConfig";
import { ConnectScreen } from "./src/screens/ConnectScreen";
import { FleetScreen } from "./src/screens/FleetScreen";
import { AgentListScreen } from "./src/screens/AgentListScreen";
import { AgentDetailScreen } from "./src/screens/AgentDetailScreen";
import { AnswerScreen } from "./src/screens/AnswerScreen";
import { SpawnScreen } from "./src/screens/SpawnScreen";
import { SchedulesScreen } from "./src/screens/SchedulesScreen";
import { MemoryScreen } from "./src/screens/MemoryScreen";
import { LogScreen } from "./src/screens/LogScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";

function Router() {
  const { screen } = useAppState();

  const screens: Record<ScreenName, () => React.JSX.Element> = {
    connect: ConnectScreen,
    fleet: FleetScreen,
    agentList: AgentListScreen,
    detail: AgentDetailScreen,
    answer: AnswerScreen,
    spawn: SpawnScreen,
    schedules: SchedulesScreen,
    memory: MemoryScreen,
    log: LogScreen,
    settings: SettingsScreen,
    manage: ManageScreen,
    models: ModelsScreen,
    skills: SkillsScreen,
    connectors: ConnectorsScreen,
    plugins: PluginsScreen,
    permissions: PermissionsScreen,
    repositories: RepositoriesScreen,
    gitServers: GitServersScreen,
    approvals: ApprovalsScreen,
    activity: ActivityScreen,
    shared: SharedContextScreen,
    users: UsersScreen,
    account: AccountScreen,
    claudeLogin: ClaudeLoginScreen,
  };
  const Screen = screens[screen];

  return <Screen />;
}

/** Gate: splash while config loads, ConnectScreen when unconfigured, else the fleet app. */
function Gate() {
  const { config, loading } = useServerConfig();
  const { scheme, colors } = useTheme();

  return (
    <View style={{ flex: 1, backgroundColor: colors.surfacePage }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      {loading ? (
        <SplashPlaceholder />
      ) : config ? (
        <AppStateProvider>
          <Router />
        </AppStateProvider>
      ) : (
        <ConnectScreen />
      )}
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
        <ServerConfigProvider>
          <Gate />
        </ServerConfigProvider>
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
