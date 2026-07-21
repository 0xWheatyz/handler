import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * Persists the one thing the app needs to talk to a Handler server — the base
 * endpoint and the bearer token — to AsyncStorage under a single versioned key.
 *
 * `config` is null until either the stored value loads (once `loading` flips
 * false) or the operator connects. A persistent 401 calls `clear()`, dropping
 * back to the ConnectScreen while `lastEndpoint` keeps the URL prefilled so the
 * operator only re-enters the token.
 */

const STORAGE_KEY = "handler.server.v1";
export const DEFAULT_ENDPOINT = "https://handler.home.leeworks.dev";

export interface ServerConfig {
  endpoint: string;
  token: string;
}

interface ServerConfigValue {
  config: ServerConfig | null;
  loading: boolean;
  /** The last endpoint we saw, for prefilling ConnectScreen after a sign-out / 401. */
  lastEndpoint: string;
  save: (config: ServerConfig) => Promise<void>;
  clear: () => Promise<void>;
}

const ServerConfigContext = createContext<ServerConfigValue | null>(null);

export function ServerConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastEndpoint, setLastEndpoint] = useState(DEFAULT_ENDPOINT);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (active && raw) {
          const parsed = JSON.parse(raw) as ServerConfig;
          if (parsed && parsed.endpoint && parsed.token) {
            setConfig(parsed);
            setLastEndpoint(parsed.endpoint);
          }
        }
      } catch {
        /* corrupt/unreadable storage — treat as unconfigured */
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const save = useCallback(async (next: ServerConfig) => {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setConfig(next);
    setLastEndpoint(next.endpoint);
  }, []);

  const clear = useCallback(async () => {
    await AsyncStorage.removeItem(STORAGE_KEY);
    setConfig(null);
  }, []);

  return (
    <ServerConfigContext.Provider
      value={{ config, loading, lastEndpoint, save, clear }}
    >
      {children}
    </ServerConfigContext.Provider>
  );
}

export function useServerConfig(): ServerConfigValue {
  const ctx = useContext(ServerConfigContext);
  if (!ctx)
    throw new Error("useServerConfig must be used within ServerConfigProvider");
  return ctx;
}
