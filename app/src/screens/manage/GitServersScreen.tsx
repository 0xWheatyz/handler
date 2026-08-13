import React, { useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { fonts, radius, text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { Select } from "../../components/Select";
import { Switch } from "../../components/Switch";
import { TextField } from "../../components/TextField";
import { Card, Divider, Mono, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import type { Host } from "../../api/client";

/**
 * Git servers — one entry per forge host, carrying the server's own
 * credentials: a forge token (encrypted at rest, write-only) and an ed25519
 * deploy keypair whose public half is shown here for the operator to paste
 * into the forge. Projects on a configured server need no per-repo
 * credentials. Writes are admin-only; 403s surface inline.
 */

const FORGE_OPTIONS = ["github", "gitlab", "gitea", "forgejo", "bitbucket"];

export function GitServersScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();
  const { data, error: loadError, loading, reload } = useResource<Host[]>("/hosts");
  const hosts = data ?? [];

  const [showForm, setShowForm] = useState(false);
  const [hostname, setHostname] = useState("");
  const [forgeType, setForgeType] = useState("github");
  const [baseUrl, setBaseUrl] = useState("");
  const [token, setToken] = useState("");
  const [generateKey, setGenerateKey] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function add() {
    if (!client) return;
    if (!hostname.trim()) {
      setError("Hostname is required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await client.api<Host>("/hosts", {
        body: {
          hostname: hostname.trim(),
          forge_type: forgeType,
          base_url: baseUrl.trim() || undefined,
          token: token || undefined,
          generate_ssh_key: generateKey,
        },
      });
      setHostname("");
      setBaseUrl("");
      setToken("");
      setGenerateKey(true);
      setShowForm(false);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t add the git server.");
    } finally {
      setBusy(false);
    }
  }

  function confirmDelete(h: Host) {
    Alert.alert(
      "Delete git server?",
      `Remove ${h.hostname} and its stored credentials. Projects on it lose their token + deploy key.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            client
              ?.api(`/hosts/${encodeURIComponent(h.hostname)}`, { method: "DELETE" })
              .then(() => reload())
              .catch((e) =>
                setError(e instanceof Error ? e.message : "Delete failed."),
              );
          },
        },
      ],
    );
  }

  return (
    <ManageShell
      title="Git servers"
      subtitle="Each server carries its own credentials: a forge token used by agents, and an SSH deploy key — paste the public half into the forge."
    >
      <View style={styles.headRow}>
        <SectionLabel>
          {`${hosts.length} server${hosts.length === 1 ? "" : "s"}`}
        </SectionLabel>
        <Button
          size="sm"
          variant={showForm ? "secondary" : "primary"}
          onPress={() => setShowForm((v) => !v)}
        >
          {showForm ? "Cancel" : "New"}
        </Button>
      </View>

      {showForm ? (
        <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
          <Field label="Hostname">
            <TextField
              value={hostname}
              onChangeText={setHostname}
              placeholder="github.com"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Select
            label="Forge type"
            options={FORGE_OPTIONS}
            value={forgeType}
            onChange={setForgeType}
          />
          <Field label="Base URL" hint="Optional — for self-hosted forges.">
            <TextField
              value={baseUrl}
              onChangeText={setBaseUrl}
              placeholder="https://git.corp.internal:8443"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
            />
          </Field>
          <Field label="Forge token" hint="Optional — encrypted at rest, never returned.">
            <TextField
              value={token}
              onChangeText={setToken}
              placeholder="used by agents’ forge + git"
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={[text.label, { color: colors.textHeading }]}>
                Generate deploy key
              </Text>
              <Text style={[text.caption, { color: colors.textMuted, marginTop: 2 }]}>
                The server mints an ed25519 keypair; the public half appears in
                the list below.
              </Text>
            </View>
            <Switch value={generateKey} onValueChange={setGenerateKey} />
          </View>
          <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : add}>
            {busy ? "Adding…" : "Add server"}
          </Button>
        </Card>
      ) : null}

      <ErrorNotice message={error ?? loadError} />

      {loading && hosts.length === 0 ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>Loading…</Text>
      ) : hosts.length === 0 ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          No git servers registered (the built-in host map still applies).
        </Text>
      ) : (
        <Card>
          {hosts.map((h, i) => (
            <View key={h.hostname}>
              {i > 0 && <Divider />}
              <View style={styles.row}>
                <View style={styles.head}>
                  <View style={{ flex: 1, gap: 4 }}>
                    <View style={styles.titleRow}>
                      <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                        {h.hostname}
                      </Mono>
                      <Badge tone="neutral">{h.forge_type}</Badge>
                    </View>
                    {h.base_url ? (
                      <Mono
                        numberOfLines={1}
                        style={{ fontSize: 12, color: colors.textMuted }}
                      >
                        {h.base_url}
                      </Mono>
                    ) : null}
                    {h.has_token ? (
                      <Text style={[text.caption, { color: colors.textMuted }]}>
                        token stored
                      </Text>
                    ) : null}
                  </View>
                  <Button size="sm" variant="danger" onPress={() => confirmDelete(h)}>
                    Delete
                  </Button>
                </View>
                {h.ssh_public_key ? (
                  <View style={{ gap: 6 }}>
                    <Text style={[text.caption, { color: colors.textMuted }]}>
                      SSH public key — add it to the forge as a deploy key
                    </Text>
                    {/* Mono doesn't pass `selectable` through, so a plain Text here
                        lets the operator long-press to copy the key. */}
                    <View
                      style={[
                        styles.keyBox,
                        {
                          backgroundColor: colors.surfaceSunken,
                          borderColor: colors.borderSubtle,
                        },
                      ]}
                    >
                      <Text
                        selectable
                        style={[styles.keyText, { color: colors.textBody }]}
                      >
                        {h.ssh_public_key}
                      </Text>
                    </View>
                  </View>
                ) : null}
              </View>
            </View>
          ))}
        </Card>
      )}
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  headRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  row: {
    gap: 10,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  head: {
    flexDirection: "row",
    gap: 12,
    alignItems: "flex-start",
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  keyBox: {
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: 8,
  },
  keyText: {
    fontFamily: fonts.monoRegular,
    fontSize: 11,
    lineHeight: 15,
  },
});
