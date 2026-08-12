/* Auth frame: sign-in gate → shell. Lives in the root layout so it wraps every page and
 * persists across client-side navigation. Client-only; the exported HTML is a shell and
 * every byte of data is fetched by the browser from the authed API after sign-in. The
 * bearer is a user session token from /auth/login (or a raw legacy API token via the
 * gate's fallback) — either way it rides Authorization on every call, and a 401 clears
 * it and re-prompts. The /reset route is public (it's how invite/reset links land). */
"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { DashboardProvider } from "@/components/store";
import { Shell } from "@/components/Shell";
import { AuthGate } from "@/components/AuthGate";
import { sectionFromPath } from "@/lib/nav";
import { type SessionResponse } from "@/lib/api";

const TOKEN_KEY = "handler_token";

export function AppFrame({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState("");
  const pathname = usePathname();

  // Read the stored token after mount (localStorage is client-only).
  useEffect(() => {
    const stored = window.localStorage.getItem(TOKEN_KEY);
    if (stored) setToken(stored);
  }, []);

  const saveToken = useCallback((t: string) => {
    window.localStorage.setItem(TOKEN_KEY, t);
    setError("");
    setToken(t);
  }, []);

  const onSession = useCallback(
    (s: SessionResponse) => {
      saveToken(s.token);
    },
    [saveToken],
  );

  const signOut = useCallback(() => {
    const t = window.localStorage.getItem(TOKEN_KEY);
    if (t) {
      // Best-effort server-side revocation; a legacy env token treats this as a no-op.
      void fetch("/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${t}` },
      }).catch(() => undefined);
    }
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }, []);

  const onUnauthorized = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setError("Session expired or token rejected — please sign in again.");
  }, []);

  // Invite/reset links must render without a session — that's their whole point.
  const isPublicRoute = pathname.replace(/\/+$/, "") === "/reset";
  if (isPublicRoute) {
    return <>{children}</>;
  }

  if (!token) {
    return <AuthGate error={error} onSession={onSession} onToken={saveToken} />;
  }

  return (
    <DashboardProvider
      token={token}
      onUnauthorized={onUnauthorized}
      initialSection={sectionFromPath(pathname)}
    >
      <Shell onSignOut={signOut}>{children}</Shell>
    </DashboardProvider>
  );
}
