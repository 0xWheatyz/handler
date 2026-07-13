/* Claude Login — drive the bundled `claude /login` OAuth flow on the host from the web UI.
 *
 * Click "Log in to Claude" → the worker opens `claude /login` in the control container,
 * selects the subscription account, and returns the claude.com authorization URL. That URL
 * is shown in an embedded frame (and as a new-tab link, since claude.com may refuse to be
 * framed); after authorizing, paste the code back to finish. All state lives in the store's
 * `claudeLogin` machine (login_start / login_submit commands). */
"use client";

import { useState } from "react";
import { useDashboard } from "@/components/store";
import { Button, Callout, Input } from "@/components/ui";

export function LoginSection() {
  const s = useDashboard();
  const { status, url, message } = s.claudeLogin;
  const [code, setCode] = useState("");

  const busy = status === "starting" || status === "submitting";
  const awaiting = status === "awaiting" || status === "submitting";

  const submit = async () => {
    const ok = await s.submitClaudeCode(code);
    if (ok) setCode("");
  };

  return (
    <>
      <div className="section-head">
        <div className="section-title">Claude Login</div>
        <div className="section-desc">
          Log Claude Code in on the host so agents can run. This drives{" "}
          <span className="mono">claude /login</span> in the control container and picks the
          Claude account with a subscription.
        </div>
      </div>

      <div className="section-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {message && (
          <Callout tone={status === "error" ? "danger" : status === "done" ? "success" : "info"}>
            {message}
          </Callout>
        )}

        {status === "done" ? (
          <div>
            <Button variant="secondary" onClick={s.resetClaudeLogin}>
              Log in again
            </Button>
          </div>
        ) : !awaiting ? (
          <div className="hstack" style={{ gap: 10 }}>
            <Button variant="primary" disabled={busy} onClick={s.startClaudeLogin}>
              {status === "starting" ? "Starting…" : "Log in to Claude"}
            </Button>
            {status === "error" && (
              <Button variant="ghost" disabled={busy} onClick={s.startClaudeLogin}>
                Retry
              </Button>
            )}
          </div>
        ) : (
          <>
            <div className="hstack" style={{ gap: 10, flexWrap: "wrap" }}>
              <a className="btn btn-secondary" href={url} target="_blank" rel="noopener noreferrer">
                Open login page in a new tab ↗
              </a>
              <Button variant="ghost" disabled={busy} onClick={s.startClaudeLogin}>
                Restart
              </Button>
            </div>

            <div
              style={{
                border: "1px solid var(--border-default)",
                borderRadius: 10,
                overflow: "hidden",
                height: 460,
                background: "var(--surface-1, #111)",
              }}
            >
              <iframe
                title="Claude login"
                src={url}
                style={{ width: "100%", height: "100%", border: "none" }}
                sandbox="allow-forms allow-scripts allow-same-origin allow-popups"
              />
            </div>
            <div className="faint" style={{ fontSize: "var(--text-xs)" }}>
              If the frame stays blank, claude.com is refusing to be embedded — use the
              new-tab link above instead. The login session stays open until you submit the
              code or restart.
            </div>

            <div className="hstack" style={{ gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 320px" }}>
                <Input
                  label="Authorization code"
                  value={code}
                  onChange={setCode}
                  placeholder="Paste the code from claude.com"
                  disabled={status === "submitting"}
                />
              </div>
              <Button
                variant="primary"
                disabled={status === "submitting" || !code.trim()}
                onClick={submit}
              >
                {status === "submitting" ? "Submitting…" : "Finish login"}
              </Button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
