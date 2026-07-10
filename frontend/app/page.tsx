/* Root page: token gate → dashboard. Client-only; the exported HTML is a shell and every
 * byte of data is fetched by the browser from the authed API after the token is supplied. */
"use client";

import { useCallback, useEffect, useState } from "react";
import { DashboardProvider } from "@/components/store";
import { Dashboard } from "@/components/Dashboard";
import { TokenGate } from "@/components/TokenGate";

const TOKEN_KEY = "handler_token";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState("");

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

  const signOut = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }, []);

  // A 401 from any call clears the token and re-prompts with an error.
  const onUnauthorized = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setError("Invalid token — please try again.");
  }, []);

  if (!token) {
    return <TokenGate error={error} onSubmit={saveToken} />;
  }

  return (
    <DashboardProvider token={token} onUnauthorized={onUnauthorized}>
      <Dashboard onSignOut={signOut} />
    </DashboardProvider>
  );
}
