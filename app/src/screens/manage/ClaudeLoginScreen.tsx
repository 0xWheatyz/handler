import React, { useState } from "react";
import { Linking, StyleSheet, Text, View } from "react-native";
import { radius, text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Button } from "../../components/Button";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { Mono } from "../../components/primitives";
import { TextField } from "../../components/TextField";
import { useAppState } from "../../state/AppState";
import type { Command } from "../../api/client";

/**
 * Claude login — sign the control container's `claude` binary into a Claude
 * subscription, phone edition of the web dashboard's login flow. Both steps are
 * control commands the worker executes (the API container has no claude binary):
 * login_start scrapes the authorization URL out of `claude /login`, the operator
 * authorizes in the browser and pastes the code back, login_submit feeds it to the
 * waiting tmux session. Admin-gated server-side.
 */

type Phase =
  | { step: "idle" }
  | { step: "starting" }
  | { step: "awaiting"; url: string }
  | { step: "submitting"; url: string }
  | { step: "done" };

export function ClaudeLoginScreen() {
  const { colors } = useTheme();
  const { client } = useAppState();

  const [phase, setPhase] = useState<Phase>({ step: "idle" });
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function start() {
    if (!client) return;
    setError(null);
    setPhase({ step: "starting" });
    try {
      const cmd = await client.api<Command>("/login/start", { method: "POST" });
      // login_start boots claude, drives the menu, and scrapes the URL — allow ~90s
      // (worker claim latency + boot waits + URL timeout).
      const final = await client.trackCommand(cmd.id, { attempts: 180 });
      if (!final) {
        setError("Still starting — is the control worker running?");
        setPhase({ step: "idle" });
        return;
      }
      if (final.status !== "done") {
        setError(final.error || "Failed to start the login.");
        setPhase({ step: "idle" });
        return;
      }
      const url =
        final.result && typeof final.result.url === "string" ? final.result.url : "";
      if (!url) {
        setError("No login URL was returned by claude.");
        setPhase({ step: "idle" });
        return;
      }
      setPhase({ step: "awaiting", url });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start the login.");
      setPhase({ step: "idle" });
    }
  }

  async function submit() {
    if (!client || phase.step !== "awaiting") return;
    const trimmed = code.trim();
    if (!trimmed) {
      setError("Paste the authorization code first.");
      return;
    }
    setError(null);
    setPhase({ step: "submitting", url: phase.url });
    try {
      const cmd = await client.api<Command>("/login/submit", {
        method: "POST",
        body: { code: trimmed },
      });
      const final = await client.trackCommand(cmd.id, { attempts: 60 });
      if (!final) {
        setError("Submit still running — is the control worker running?");
        setPhase({ step: "awaiting", url: phase.url });
        return;
      }
      if (final.status === "done") {
        setCode("");
        setPhase({ step: "done" });
        return;
      }
      setError(final.error || "Login was not confirmed. Re-check the code or restart.");
      setPhase({ step: "awaiting", url: phase.url });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't submit the code.");
      setPhase({ step: "awaiting", url: phase.url });
    }
  }

  return (
    <ManageShell
      title="Claude login"
      subtitle="Sign the control container's claude binary into a Claude subscription. New agents launch on whichever account is logged in."
    >
      <ErrorNotice message={error} />

      {phase.step === "idle" || phase.step === "starting" ? (
        <Button
          size="lg"
          style={{ width: "100%" }}
          onPress={phase.step === "starting" ? undefined : start}
        >
          {phase.step === "starting" ? "Starting claude /login…" : "Start login"}
        </Button>
      ) : null}

      {phase.step === "awaiting" || phase.step === "submitting" ? (
        <View style={{ gap: 16 }}>
          <View
            style={[
              styles.urlBox,
              { backgroundColor: colors.surfaceSunken, borderColor: colors.borderSubtle },
            ]}
          >
            <Text style={[text.bodySm, { color: colors.textBody, marginBottom: 8 }]}>
              Authorize at this URL, then paste the code claude gives you:
            </Text>
            <Text selectable style={[styles.urlText, { color: colors.textMuted }]}>
              {phase.url}
            </Text>
          </View>
          <Button
            variant="secondary"
            style={{ width: "100%" }}
            onPress={() => void Linking.openURL(phase.url)}
          >
            Open in browser
          </Button>
          <Field label="Authorization code">
            <TextField
              value={code}
              onChangeText={setCode}
              placeholder="Paste the code from claude.com"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </Field>
          <Button
            size="lg"
            style={{ width: "100%" }}
            onPress={phase.step === "submitting" ? undefined : submit}
          >
            {phase.step === "submitting" ? "Submitting…" : "Submit code"}
          </Button>
        </View>
      ) : null}

      {phase.step === "done" ? (
        <View style={{ gap: 16 }}>
          <View
            style={[
              styles.urlBox,
              { backgroundColor: colors.positiveTint, borderColor: colors.positive },
            ]}
          >
            <Text style={[text.bodySm, { color: colors.positive }]}>
              Claude Code is now logged in on the host — new agents will use this
              account.
            </Text>
          </View>
          <Button variant="secondary" style={{ width: "100%" }} onPress={start}>
            Log in again
          </Button>
        </View>
      ) : null}

      <Mono style={{ fontSize: 12, color: colors.textMuted, marginTop: 20 }}>
        The URL opens claude.com; authorize with the subscription account you want
        agents to run on.
      </Mono>
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  urlBox: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
  },
  urlText: {
    fontSize: 12,
    lineHeight: 17,
  },
});
