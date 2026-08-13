import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Icon } from "../../components/Icon";
import { ManageShell } from "../../components/ManageShell";
import { Card, Divider, SectionLabel } from "../../components/primitives";
import { useAppState, type Screen } from "../../state/AppState";

/**
 * The management hub (Settings → Manage): the mobile counterpart of the web
 * dashboard's admin surface. Most actions here need the admin token (or an
 * admin account session); non-admin sessions get inline 403s on writes.
 */

interface Row {
  screen: Screen;
  title: string;
  subtitle: string;
}

const CLAUDE_ROWS: Row[] = [
  { screen: "models", title: "Models", subtitle: "Model backends for spawns + schedules" },
  { screen: "skills", title: "Skills", subtitle: "Managed skills synced to every worker" },
  { screen: "connectors", title: "Connectors", subtitle: "MCP servers agents may reach" },
  { screen: "plugins", title: "Plugins", subtitle: "Marketplace plugins installed on boot" },
  { screen: "permissions", title: "Permissions", subtitle: "Default mode + allow/deny/ask rules" },
  { screen: "claudeLogin", title: "Claude login", subtitle: "Sign the worker into Claude Code" },
];

const SERVER_ROWS: Row[] = [
  { screen: "repositories", title: "Repositories", subtitle: "Register + sync project repos" },
  { screen: "gitServers", title: "Git servers", subtitle: "Forge hosts, tokens, deploy keys" },
  { screen: "approvals", title: "Approvals", subtitle: "Approve or reject protected branches" },
  { screen: "shared", title: "Shared context", subtitle: "Key/value context all agents see" },
  { screen: "users", title: "Users", subtitle: "Invite, promote, disable, reset" },
];

export function ManageScreen() {
  return (
    <ManageShell
      title="Manage"
      subtitle="The full control surface — everything the web dashboard can do."
      backTo="settings"
    >
      <SectionLabel style={{ marginBottom: 8 }}>Claude</SectionLabel>
      <RowsCard rows={CLAUDE_ROWS} />
      <SectionLabel style={{ marginTop: 20, marginBottom: 8 }}>Server</SectionLabel>
      <RowsCard rows={SERVER_ROWS} />
    </ManageShell>
  );
}

function RowsCard({ rows }: { rows: Row[] }) {
  const { colors } = useTheme();
  const { go } = useAppState();
  return (
    <Card>
      {rows.map((r, i) => (
        <View key={r.screen}>
          {i > 0 && <Divider />}
          <Pressable style={styles.row} onPress={() => go(r.screen)}>
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={[text.label, { color: colors.textHeading }]}>{r.title}</Text>
              <Text style={[text.caption, { color: colors.textMuted }]}>
                {r.subtitle}
              </Text>
            </View>
            <Icon name="chevronRight" size={16} color={colors.textMuted} />
          </Pressable>
        </View>
      ))}
    </Card>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 44,
  },
});
