/* Token gate: shown until an API token is supplied. Holds no data. Management actions
 * (spawn, approve, edit repos/servers) need the admin token; read-only views need the
 * plain auth token. The token lives only in localStorage on this device. */
"use client";

import { useState } from "react";

export function TokenGate({ error, onSubmit }: { error?: string; onSubmit: (token: string) => void }) {
  const [value, setValue] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = value.trim();
    if (t) onSubmit(t);
  };

  return (
    <div className="gate">
      <form className="gate-card" onSubmit={submit}>
        <div className="gate-brand">
          <span className="logo" style={{ width: 26, height: 26, borderRadius: 7 }} />
          Claude Monitor
        </div>
        <p className="muted" style={{ fontSize: "var(--text-sm)", margin: 0 }}>
          Paste your API token to continue. Management actions require the admin token; read-only
          views work with the plain auth token.
        </p>
        <input
          className="input"
          type="password"
          autoComplete="current-password"
          placeholder="API token"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoFocus
        />
        {error && (
          <p className="callout callout-danger" style={{ margin: 0 }}>
            {error}
          </p>
        )}
        <button className="btn btn-primary" type="submit">
          Continue
        </button>
      </form>
    </div>
  );
}
