/* Public set-password page — where invite and reset links land (/reset?token=…).
 * Outside the auth gate by design: the person arriving here has no session yet.
 * Success stores the fresh session token and drops the user into the dashboard. */
"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { authApi, type ApiError, type SessionResponse } from "@/lib/api";

function ResetForm() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      const session = await authApi<SessionResponse>("/auth/reset", { token, password });
      window.localStorage.setItem("handler_token", session.token);
      router.replace("/");
    } catch (err) {
      setError((err as ApiError).message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="gate">
      <form className="gate-card" onSubmit={submit}>
        <div className="gate-brand">
          <span className="logo" style={{ width: 26, height: 26, borderRadius: 7 }} />
          Claude Monitor
        </div>
        {token ? (
          <>
            <p className="muted" style={{ fontSize: "var(--text-sm)", margin: 0 }}>
              Choose a password for your account. The link you followed is one-shot — once
              set, sign in with your email and this password.
            </p>
            <input
              className="input"
              type="password"
              autoComplete="new-password"
              placeholder="New password (8+ characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              autoFocus
              required
            />
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
            {error && (
              <p className="callout callout-danger" style={{ margin: 0 }}>
                {error}
              </p>
            )}
            <button className="btn btn-primary" type="submit" disabled={busy}>
              Set password and sign in
            </button>
          </>
        ) : (
          <p className="callout callout-danger" style={{ margin: 0 }}>
            This page needs a reset link (…/reset?token=…). Ask an admin for one, or use
            “Forgot password?” on the sign-in page.
          </p>
        )}
      </form>
    </div>
  );
}

export default function ResetPage() {
  // useSearchParams requires a Suspense boundary under the static export.
  return (
    <Suspense fallback={null}>
      <ResetForm />
    </Suspense>
  );
}
