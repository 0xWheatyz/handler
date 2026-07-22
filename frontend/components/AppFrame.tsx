/* Auth frame: token gate → shell. Lives in the root layout so it wraps every page and
 * persists across client-side navigation. Client-only; the exported HTML is a shell and
 * every byte of data is fetched by the browser from the authed API after the token is
 * supplied. A 401 from any call clears the token and re-prompts with an error. */
"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { DashboardProvider } from "@/components/store";
import { Shell } from "@/components/Shell";
import { TokenGate } from "@/components/TokenGate";
import { sectionFromPath } from "@/lib/nav";

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

  const signOut = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }, []);

  const onUnauthorized = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setError("Invalid token — please try again.");
  }, []);

  if (!token) {
    return <TokenGate error={error} onSubmit={saveToken} />;
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
