/* Auth gate: email + password sign-in, shown until a session exists. On a fresh
 * deployment (no accounts yet) it becomes the first-run setup form — the account
 * created there is the admin. A collapsible fallback still accepts a raw API token
 * for headless/legacy setups. Holds no data; the session token lives in localStorage. */
"use client";

import { useEffect, useState } from "react";
import { authApi, type ApiError, type AuthStatus, type SessionResponse } from "@/lib/api";

type Mode = "loading" | "setup" | "login" | "forgot" | "token";

export function AuthGate({
  error,
  onSession,
  onToken,
}: {
  error?: string;
  /* A fresh session from login/setup: token + user. */
  onSession: (s: SessionResponse) => void;
  /* Raw API-token fallback (legacy/scripts). */
  onToken: (token: string) => void;
}) {
  const [mode, setMode] = useState<Mode>("loading");
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [rawToken, setRawToken] = useState("");
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState(error ?? "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    authApi<AuthStatus>("/auth/status")
      .then((s) => {
        setStatus(s);
        setMode(s.initialized ? "login" : "setup");
      })
      .catch(() => {
        // API unreachable or very old server — fall back to the raw token prompt.
        setMode("token");
      });
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    setMessage("");
    if (mode === "token") {
      if (rawToken.trim()) onToken(rawToken.trim());
      return;
    }
    setBusy(true);
    try {
      if (mode === "setup") {
        if (password !== confirm) {
          setFormError("Passwords don't match.");
          return;
        }
        onSession(await authApi<SessionResponse>("/auth/setup", { email, password }));
      } else if (mode === "login") {
        onSession(await authApi<SessionResponse>("/auth/login", { email, password }));
      } else if (mode === "forgot") {
        const r = await authApi<{ ok: boolean; emailed: boolean }>("/auth/forgot", { email });
        setMessage(
          r.emailed
            ? "If that address has an account, a reset link is on its way."
            : "Email isn't configured on this deployment — ask an admin to generate a reset link for you.",
        );
      }
    } catch (err) {
      setFormError((err as ApiError).message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  if (mode === "loading") {
    return (
      <div className="gate">
        <div className="gate-card">
          <div className="gate-brand">
            <span className="logo" style={{ width: 26, height: 26, borderRadius: 7 }} />
            Claude Monitor
          </div>
          <p className="muted" style={{ fontSize: "var(--text-sm)", margin: 0 }}>
            Loading…
          </p>
        </div>
      </div>
    );
  }

  const heading =
    mode === "setup"
      ? "Welcome — create the first account. It becomes the admin; everyone else is invited by you."
      : mode === "forgot"
        ? "Enter your account email and we'll send a password reset link."
        : mode === "token"
          ? "Paste a raw API token (legacy / script access)."
          : "Sign in with your email and password.";

  return (
    <div className="gate">
      <form className="gate-card" onSubmit={submit}>
        <div className="gate-brand">
          <span className="logo" style={{ width: 26, height: 26, borderRadius: 7 }} />
          Claude Monitor
        </div>
        <p className="muted" style={{ fontSize: "var(--text-sm)", margin: 0 }}>
          {heading}
        </p>

        {mode !== "token" && (
          <input
            className="input"
            type="email"
            autoComplete="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoFocus
            required
          />
        )}
        {(mode === "login" || mode === "setup") && (
          <input
            className="input"
            type="password"
            autoComplete={mode === "setup" ? "new-password" : "current-password"}
            placeholder={mode === "setup" ? "Password (8+ characters)" : "Password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        )}
        {mode === "setup" && (
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            placeholder="Confirm password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            minLength={8}
            required
          />
        )}
        {mode === "token" && (
          <input
            className="input"
            type="password"
            autoComplete="off"
            placeholder="API token"
            value={rawToken}
            onChange={(e) => setRawToken(e.target.value)}
            autoFocus
          />
        )}

        {formError && (
          <p className="callout callout-danger" style={{ margin: 0 }}>
            {formError}
          </p>
        )}
        {message && (
          <p className="callout callout-info" style={{ margin: 0 }}>
            {message}
          </p>
        )}

        <button className="btn btn-primary" type="submit" disabled={busy}>
          {mode === "setup"
            ? "Create admin account"
            : mode === "forgot"
              ? "Send reset link"
              : mode === "token"
                ? "Continue"
                : "Sign in"}
        </button>

        <div
          className="hstack muted"
          style={{ justifyContent: "space-between", fontSize: "var(--text-xs)" }}
        >
          {mode === "login" && (
            <button type="button" className="btn-link" onClick={() => setMode("forgot")}>
              Forgot password?
            </button>
          )}
          {(mode === "forgot" || mode === "token") && status?.initialized !== false && (
            <button type="button" className="btn-link" onClick={() => setMode("login")}>
              Back to sign in
            </button>
          )}
          {mode !== "token" && (
            <button type="button" className="btn-link" onClick={() => setMode("token")}>
              Use an API token
            </button>
          )}
          {mode === "token" && status?.initialized === false && (
            <button type="button" className="btn-link" onClick={() => setMode("setup")}>
              Back to setup
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
