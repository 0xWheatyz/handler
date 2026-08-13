import React, { useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { fonts, text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Switch } from "../../components/Switch";
import { TextField } from "../../components/TextField";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { Card, Divider, Mono, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import { timeAgo } from "../../api/format";
import { AuthError, type ResetLink, type User, type UserCreated } from "../../api/client";

/**
 * Users — admin-only account management (Settings → Manage → Users), the mobile
 * counterpart of the web dashboard's Users section. Invite by email (the invitee
 * sets their own password through a one-shot link, emailed when SMTP is configured
 * and always shown here), toggle admin/disabled, mint reset links, delete. The
 * server guards the last active admin and self-deletes; those refusals surface
 * inline. A non-admin session gets a 403 on the list itself.
 */

/* The invite/reset link the last mutation minted, kept visible until the next one. */
interface LastLink {
  email: string;
  url: string;
  emailed: boolean;
}

export function UsersScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();
  const { data: users, error: listError, loading, reload } = useResource<User[]>(
    "/auth/users",
  );

  const [email, setEmail] = useState("");
  const [inviteAdmin, setInviteAdmin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastLink, setLastLink] = useState<LastLink | null>(null);

  async function invite() {
    if (!client) return;
    if (!email.trim()) {
      setError("An email address is required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const created = await client.api<UserCreated>("/auth/users", {
        body: { email: email.trim(), is_admin: inviteAdmin },
      });
      setLastLink({
        email: created.user.email,
        url: created.invite_url,
        emailed: created.emailed,
      });
      setEmail("");
      setInviteAdmin(false);
      reload();
    } catch (e) {
      if (e instanceof AuthError) return; // handled by onUnauthorized
      setError(e instanceof Error ? e.message : "Invite failed.");
    } finally {
      setBusy(false);
    }
  }

  async function patchUser(id: number, fields: Partial<Pick<User, "is_admin" | "disabled">>) {
    if (!client) return;
    setError(null);
    try {
      await client.api<User>(`/auth/users/${id}`, { method: "PATCH", body: fields });
      reload();
    } catch (e) {
      if (e instanceof AuthError) return;
      setError(e instanceof Error ? e.message : "Update failed.");
    }
  }

  async function mintResetLink(u: User) {
    if (!client) return;
    setError(null);
    try {
      const link = await client.api<ResetLink>(`/auth/users/${u.id}/reset-link`, {
        method: "POST",
      });
      setLastLink({ email: u.email, url: link.reset_url, emailed: link.emailed });
    } catch (e) {
      if (e instanceof AuthError) return;
      setError(e instanceof Error ? e.message : "Couldn’t mint a reset link.");
    }
  }

  function confirmDelete(u: User) {
    Alert.alert(
      "Remove user?",
      `Remove ${u.email}. Their projects, skills, and tools become shared.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: () => {
            if (!client) return;
            client
              .api(`/auth/users/${u.id}`, { method: "DELETE" })
              .then(() => reload())
              .catch((e) => {
                if (e instanceof AuthError) return;
                // Server refuses last-admin and self deletes; surface its reason.
                setError(e instanceof Error ? e.message : "Delete failed.");
              });
          },
        },
      ],
    );
  }

  const count = users?.length ?? 0;

  return (
    <ManageShell
      title="Users"
      subtitle="Accounts for this Handler. Each user's projects, skills, and tools are theirs alone; shared resources are admin-managed."
    >
      <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
        <Field label="Email" hint="The invitee sets their own password through a one-shot link.">
          <TextField
            value={email}
            onChangeText={setEmail}
            placeholder="new-user@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
          />
        </Field>
        <View style={styles.switchRow}>
          <Text style={[text.label, { color: colors.textHeading }]}>Admin</Text>
          <Switch value={inviteAdmin} onValueChange={setInviteAdmin} />
        </View>
        <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : invite}>
          {busy ? "Inviting…" : "Invite user"}
        </Button>
      </Card>

      <ErrorNotice message={error} />

      {lastLink ? (
        <Card style={{ padding: 16, marginBottom: 16, gap: 8 }}>
          <Text style={[text.label, { color: colors.textHeading }]}>
            One-shot set-password link for {lastLink.email}
          </Text>
          <Text
            selectable
            style={{ fontFamily: fonts.monoRegular, fontSize: 12, color: colors.textBody }}
          >
            {lastLink.url}
          </Text>
          <Text style={[text.caption, { color: colors.textMuted }]}>
            {lastLink.emailed
              ? "Also emailed to them. It expires; share over a channel you trust."
              : "SMTP is off — hand this link over yourself. It expires."}
          </Text>
        </Card>
      ) : null}

      <SectionLabel style={{ marginBottom: 8 }}>
        {`${count} user${count === 1 ? "" : "s"}`}
      </SectionLabel>

      {listError ? (
        <ErrorNotice message={listError} />
      ) : loading && !users ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>Loading…</Text>
      ) : count === 0 ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>No users yet.</Text>
      ) : (
        <Card>
          {(users ?? []).map((u, i) => (
            <View key={u.id}>
              {i > 0 && <Divider />}
              <View style={styles.row}>
                <View style={{ flex: 1, gap: 4 }}>
                  <View style={styles.titleRow}>
                    <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                      {u.email}
                    </Mono>
                    {u.is_admin ? <Badge tone="positive">admin</Badge> : null}
                    {u.disabled ? <Badge tone="danger">disabled</Badge> : null}
                    {!u.has_password ? <Badge tone="warning">invite pending</Badge> : null}
                  </View>
                  <Text style={[text.caption, { color: colors.textMuted }]}>
                    created {timeAgo(u.created_at)} ago
                  </Text>
                  <View style={styles.switchRow}>
                    <Text style={[text.caption, { color: colors.textMuted }]}>admin</Text>
                    <Switch
                      value={u.is_admin}
                      onValueChange={(v) => void patchUser(u.id, { is_admin: v })}
                    />
                  </View>
                  <View style={styles.switchRow}>
                    <Text style={[text.caption, { color: colors.textMuted }]}>disabled</Text>
                    <Switch
                      value={u.disabled}
                      onValueChange={(v) => void patchUser(u.id, { disabled: v })}
                    />
                  </View>
                </View>
                <View style={styles.rowActions}>
                  <Button size="sm" variant="secondary" onPress={() => void mintResetLink(u)}>
                    Reset link
                  </Button>
                  <Button size="sm" variant="danger" onPress={() => confirmDelete(u)}>
                    Delete
                  </Button>
                </View>
              </View>
            </View>
          ))}
        </Card>
      )}
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  rowActions: {
    alignItems: "flex-end",
    justifyContent: "flex-start",
    gap: 10,
  },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
});
