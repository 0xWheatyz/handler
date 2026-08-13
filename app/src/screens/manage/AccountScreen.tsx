import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { radius, text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { TextField } from "../../components/TextField";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { Card, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useServerConfig } from "../../state/ServerConfig";
import { useResource } from "../../state/useResource";
import { AuthError, type Me } from "../../api/client";

/**
 * Account (Settings → Account): who this session is, change password, sign out.
 * Sessions come in two kinds — a user account (email + password, revocable
 * sessions) or the legacy env API token (configuration, not a session): tokens
 * have no password to change and nothing server-side to revoke on sign-out.
 */

export function AccountScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();
  const { clear } = useServerConfig();
  const { data: me, error: meError, loading } = useResource<Me>("/auth/me");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function changePassword() {
    if (!client) return;
    if (!currentPassword || !newPassword) {
      setError("Both the current and the new password are required.");
      return;
    }
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await client.api("/auth/change-password", {
        body: { current_password: currentPassword, new_password: newPassword },
      });
      setCurrentPassword("");
      setNewPassword("");
      setNotice("Password changed — other sessions were signed out.");
    } catch (e) {
      if (e instanceof AuthError) return; // handled by onUnauthorized
      setError(e instanceof Error ? e.message : "Password change failed.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    // Revoke the session server-side when possible; a dead server or an env
    // token must never block the local sign-out.
    if (client) {
      try {
        await client.api("/auth/logout", { method: "POST" });
      } catch {
        /* ignore — clearing the stored config is the part that matters */
      }
    }
    await clear();
  }

  return (
    <ManageShell title="Account" backTo="settings">
      {meError ? <ErrorNotice message={meError} /> : null}

      <SectionLabel style={{ marginBottom: 8 }}>Signed in as</SectionLabel>
      <Card style={{ padding: 16, marginBottom: 20, gap: 8 }}>
        {loading && !me ? (
          <Text style={[text.bodySm, { color: colors.textMuted }]}>Loading…</Text>
        ) : (
          <>
            <Text style={[text.body, { color: colors.textHeading }]}>
              {me?.kind === "token" ? "legacy API token" : me?.email ?? "—"}
            </Text>
            <View style={styles.badgeRow}>
              <Badge tone={me?.is_admin ? "positive" : "neutral"}>
                {me?.is_admin ? "admin" : "member"}
              </Badge>
            </View>
          </>
        )}
      </Card>

      <SectionLabel style={{ marginBottom: 8 }}>Change password</SectionLabel>
      {me?.kind === "token" ? (
        <Text style={[text.bodySm, { color: colors.textMuted, marginBottom: 20 }]}>
          Env tokens have no password — this session authenticates with the
          server's configured API token.
        </Text>
      ) : (
        <Card style={{ padding: 16, marginBottom: 20, gap: 14 }}>
          <Field label="Current password">
            <TextField
              value={currentPassword}
              onChangeText={setCurrentPassword}
              placeholder="••••••••"
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Field label="New password">
            <TextField
              value={newPassword}
              onChangeText={setNewPassword}
              placeholder="••••••••"
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <ErrorNotice message={error} />
          {notice ? (
            <View
              style={[
                styles.notice,
                { backgroundColor: colors.positiveTint, borderColor: colors.positive },
              ]}
            >
              <Text style={[text.bodySm, { color: colors.positive }]}>{notice}</Text>
            </View>
          ) : null}
          <Button
            size="lg"
            style={{ width: "100%" }}
            onPress={busy ? undefined : changePassword}
          >
            {busy ? "Changing…" : "Change password"}
          </Button>
        </Card>
      )}

      <Button size="lg" variant="danger" style={{ width: "100%" }} onPress={() => void signOut()}>
        Sign out
      </Button>
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  badgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  notice: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
  },
});
