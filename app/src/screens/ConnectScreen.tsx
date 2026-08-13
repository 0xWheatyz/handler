import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Button } from "../components/Button";
import { SegmentedControl } from "../components/SegmentedControl";
import { TextField } from "../components/TextField";
import { SectionLabel } from "../components/primitives";
import {
  DEFAULT_ENDPOINT,
  useServerConfig,
  type ServerConfig,
} from "../state/ServerConfig";
import {
  authApi,
  AuthError,
  createClient,
  type ApiError,
  type AuthStatus,
  type Project,
  type SessionResponse,
} from "../api/client";

/**
 * First-open configuration screen, shown whenever no server config is stored (and after
 * a Sign out or a persistent 401). Two ways in, mirroring the web dashboard's gate:
 *
 * - **Email** (default): sign in against /auth/login; the returned session token is
 *   stored and used exactly like the legacy env token. A server with zero accounts
 *   (GET /auth/status → initialized: false) flips the form into first-run setup — the
 *   account created there becomes the admin. A server predating user accounts (404 on
 *   /auth/status) falls back to the token method with a note.
 * - **API token**: the legacy env token, verified via /health + /projects before it is
 *   persisted (distinguishing an unreachable endpoint from a rejected token).
 */
export function ConnectScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { lastEndpoint, save } = useServerConfig();

  const [endpoint, setEndpoint] = useState(lastEndpoint || DEFAULT_ENDPOINT);
  const [method, setMethod] = useState<"email" | "token">("email");
  const [setup, setSetup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  function isApiError(e: unknown): e is ApiError {
    return e instanceof Error && typeof (e as ApiError).status === "number";
  }

  async function connectWithEmail(ep: string) {
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }

    // Probe first: unreachable endpoint, pre-accounts server, and first-run all
    // need different flows, and /auth/status is the unauthenticated discriminator.
    let status: AuthStatus;
    try {
      status = await authApi<AuthStatus>(ep, "/auth/status");
    } catch (e) {
      if (isApiError(e) && e.status === 404) {
        setMethod("token");
        setNote(
          "This server predates user accounts — connect with its API token instead.",
        );
        return;
      }
      setError("Couldn't reach that endpoint. Check the URL and your connection.");
      return;
    }

    if (!status.initialized) {
      if (!setup) {
        // Reveal the confirm field and let the operator opt in explicitly —
        // creating the admin account should never happen off a mistyped tap.
        setSetup(true);
        setNote(
          "This server has no accounts yet. The account you create now becomes the admin.",
        );
        return;
      }
      if (password !== confirm) {
        setError("Passwords don't match.");
        return;
      }
      const session = await authApi<SessionResponse>(ep, "/auth/setup", {
        email: email.trim(),
        password,
      });
      await save({ endpoint: ep, token: session.token });
      return;
    }

    const session = await authApi<SessionResponse>(ep, "/auth/login", {
      email: email.trim(),
      password,
    });
    await save({ endpoint: ep, token: session.token });
  }

  async function connectWithToken(ep: string) {
    const tok = token.trim();
    if (!tok) {
      setError("Enter an API token.");
      return;
    }
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
  }

  async function connect() {
    const ep = endpoint.trim();
    if (!ep) {
      setError("Enter an endpoint.");
      return;
    }
    setError(null);
    setNote(null);
    setBusy(true);
    try {
      if (method === "email") {
        await connectWithEmail(ep);
      } else {
        await connectWithToken(ep);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't connect.");
    } finally {
      setBusy(false);
    }
  }

  async function forgot() {
    const ep = endpoint.trim();
    if (!ep || !email.trim()) {
      setError("Enter the endpoint and your email first.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const res = await authApi<{ ok: boolean; emailed: boolean }>(
        ep,
        "/auth/forgot",
        { email: email.trim() },
      );
      setNote(
        res.emailed
          ? "If that address has an account, a reset link is on its way."
          : "This server has no email configured — ask an admin for a reset link.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't request a reset.");
    } finally {
      setBusy(false);
    }
  }

  const buttonLabel = busy
    ? "Connecting…"
    : setup
      ? "Create admin account"
      : method === "email"
        ? "Sign in"
        : "Connect";

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          style={styles.flex}
          contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + 20 }]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
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

            {!setup ? (
              <SegmentedControl
                segments={[
                  { value: "email", label: "Email" },
                  { value: "token", label: "API token" },
                ]}
                value={method}
                onChange={(v) => {
                  setMethod(v as "email" | "token");
                  setError(null);
                  setNote(null);
                }}
              />
            ) : null}

            {method === "email" ? (
              <>
                <View>
                  <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                    Email
                  </Text>
                  <TextField
                    value={email}
                    onChangeText={setEmail}
                    placeholder="you@example.com"
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="email-address"
                  />
                </View>
                <View>
                  <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                    Password
                  </Text>
                  <TextField
                    value={password}
                    onChangeText={setPassword}
                    placeholder="Password"
                    secureTextEntry
                    autoCapitalize="none"
                    autoCorrect={false}
                  />
                </View>
                {setup ? (
                  <View>
                    <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                      Confirm password
                    </Text>
                    <TextField
                      value={confirm}
                      onChangeText={setConfirm}
                      placeholder="Same password again"
                      secureTextEntry
                      autoCapitalize="none"
                      autoCorrect={false}
                    />
                  </View>
                ) : (
                  <Pressable onPress={busy ? undefined : forgot} hitSlop={8}>
                    <Text style={[text.bodySm, { color: colors.textMuted }]}>
                      Forgot password?
                    </Text>
                  </Pressable>
                )}
              </>
            ) : (
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
            )}

            {note ? (
              <View
                style={[
                  styles.noteBox,
                  { backgroundColor: colors.surfaceSunken, borderColor: colors.borderSubtle },
                ]}
              >
                <Text style={[text.bodySm, { color: colors.textBody }]}>{note}</Text>
              </View>
            ) : null}

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

          <View style={{ marginTop: 28 }}>
            <Button
              size="lg"
              style={{ width: "100%" }}
              onPress={busy ? undefined : connect}
            >
              {buttonLabel}
            </Button>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  flex: { flex: 1 },
  content: { flexGrow: 1, paddingTop: 8, paddingHorizontal: 20 },
  heading: { marginTop: 12, marginBottom: 24 },
  errorBox: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
  },
  noteBox: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
  },
});
