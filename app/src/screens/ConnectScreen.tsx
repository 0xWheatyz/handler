import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Button } from "../components/Button";
import { TextField } from "../components/TextField";
import { SectionLabel } from "../components/primitives";
import {
  DEFAULT_ENDPOINT,
  useServerConfig,
  type ServerConfig,
} from "../state/ServerConfig";
import { AuthError, createClient, type Project } from "../api/client";

/**
 * First-open configuration screen, shown whenever no server config is stored (and after a
 * Sign out or a persistent 401). Verifies connectivity (GET /health) and the token
 * (GET /projects) before persisting, distinguishing an unreachable endpoint from a bad
 * token in the inline error. Matches the SpawnScreen layout.
 */
export function ConnectScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { lastEndpoint, save } = useServerConfig();

  const [endpoint, setEndpoint] = useState(lastEndpoint || DEFAULT_ENDPOINT);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function connect() {
    const ep = endpoint.trim();
    const tok = token.trim();
    if (!ep) {
      setError("Enter an endpoint.");
      return;
    }
    if (!tok) {
      setError("Enter an API token.");
      return;
    }

    setError(null);
    setBusy(true);
    try {
      const client = createClient(ep, tok, () => {});

      // 1. Connectivity — /health needs no auth, so a failure here is the endpoint.
      try {
        await client.api<{ status: string }>("/health");
      } catch {
        setError("Couldn't reach that endpoint. Check the URL and your connection.");
        return;
      }

      // 2. Auth — a 401 on /projects is the token, not the endpoint.
      try {
        await client.api<Project[]>("/projects");
      } catch (e) {
        if (e instanceof AuthError) {
          setError("Token rejected. Check your API token.");
        } else {
          setError(e instanceof Error ? e.message : "Couldn't load projects.");
        }
        return;
      }

      const cfg: ServerConfig = { endpoint: ep, token: tok };
      await save(cfg);
      // The gate in App.tsx swaps this screen for the fleet once config is set.
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={[styles.content, { paddingBottom: insets.bottom + 20 }]}>
          <View style={styles.heading}>
            <Text style={[text.h3, { color: colors.textHeading }]}>Connect</Text>
            <Text style={[text.bodySm, { color: colors.textMuted, marginTop: 2 }]}>
              Point Handler at your control server.
            </Text>
          </View>

          <View style={{ gap: 16 }}>
            <View>
              <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                Endpoint
              </Text>
              <TextField
                value={endpoint}
                onChangeText={setEndpoint}
                placeholder="https://handler.example.dev"
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
              />
            </View>

            <View>
              <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                API token
              </Text>
              <TextField
                value={token}
                onChangeText={setToken}
                placeholder="Bearer token"
                secureTextEntry
                autoCapitalize="none"
                autoCorrect={false}
              />
            </View>

            {error ? (
              <View
                style={[
                  styles.errorBox,
                  { backgroundColor: colors.dangerTint, borderColor: colors.danger },
                ]}
              >
                <SectionLabel style={{ color: colors.danger, marginBottom: 4 }}>
                  Couldn’t connect
                </SectionLabel>
                <Text style={[text.bodySm, { color: colors.danger }]}>{error}</Text>
              </View>
            ) : null}
          </View>

          <View style={{ marginTop: "auto" }}>
            <Button
              size="lg"
              style={{ width: "100%" }}
              onPress={busy ? undefined : connect}
            >
              {busy ? "Connecting…" : "Connect"}
            </Button>
          </View>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  flex: { flex: 1 },
  content: { flex: 1, paddingTop: 8, paddingHorizontal: 20 },
  heading: { marginTop: 12, marginBottom: 24 },
  errorBox: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
  },
});
