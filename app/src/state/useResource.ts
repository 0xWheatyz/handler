import { useCallback, useEffect, useState } from "react";
import { AuthError } from "../api/client";
import { useAppState } from "./AppState";

/**
 * Fetch-on-mount helper for the management screens: GETs `path` through the app's
 * client, tracks loading/error, and exposes `reload` for after a mutation.
 * Pass null to fetch nothing (e.g. while a prerequisite is missing).
 */
export function useResource<T>(path: string | null): {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
} {
  const { client } = useAppState();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!client || path === null) return;
    let stale = false;
    setLoading(true);
    setError(null);
    client
      .api<T>(path)
      .then((d) => {
        if (!stale) setData(d);
      })
      .catch((e) => {
        if (e instanceof AuthError) return; // handled by onUnauthorized
        if (!stale) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!stale) setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [client, path, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, reload };
}
