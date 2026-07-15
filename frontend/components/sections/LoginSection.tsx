/* Claude Login — drive the bundled `claude /login` OAuth flow on the host from the web UI.
 *
 * Click "Log in to Claude" → a small OAuth-style popup window opens (like "Sign in with
 * Google") and the worker drives `claude /login` in the control container, selecting the
 * subscription account and returning the claude.com authorization URL, which we point the
 * popup at. (claude.com refuses to be embedded in an iframe, so a popup — not an inline
 * frame — is the right surface.) You authorize there, copy the code, and paste it back to
 * finish. All state lives in the store's `claudeLogin` machine (login_start / login_submit
 * commands). */
"use client";

import { useEffect, useRef, useState } from "react";
import { useDashboard } from "@/components/store";
import { Button, Callout, Input } from "@/components/ui";

function openLoginPopup(url: string): Window | null {
  const w = 520;
  const h = 760;
  // Center over the current window; specifying a size makes browsers open a popup window
  // (the "Sign in with …" surface) rather than a new tab.
  const left = window.screenX + Math.max(0, (window.outerWidth - w) / 2);
  const top = window.screenY + Math.max(0, (window.outerHeight - h) / 2);
  return window.open(
    url,
    "claude-login",
    `popup=yes,width=${w},height=${h},left=${Math.round(left)},top=${Math.round(top)}`,
  );
}

export function LoginSection() {
  const s = useDashboard();
  const { status, url, message } = s.claudeLogin;
  const [code, setCode] = useState("");
  const popupRef = useRef<Window | null>(null);

  const busy = status === "starting" || status === "submitting";
  const awaiting = status === "awaiting" || status === "submitting";

  // Open a blank popup *within the click* (below) so browsers don't block it; once
  // login_start returns the URL, navigate that same popup to it.
  useEffect(() => {
    if (status === "awaiting" && url && popupRef.current && !popupRef.current.closed) {
      try {
        popupRef.current.location.href = url;
      } catch {
        /* cross-origin after navigation — expected, ignore */
      }
    }
    if (status === "done" || status === "error") {
      popupRef.current?.close();
      popupRef.current = null;
    }
  }, [status, url]);

  const start = () => {
    // Open the popup now, on the user gesture, to a lightweight loading page; the effect
    // above redirects it to the real URL when it arrives.
    popupRef.current = openLoginPopup("about:blank");
    void s.startClaudeLogin();
  };

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
            <Button variant="primary" disabled={busy} onClick={start}>
              {status === "starting" ? "Starting…" : "Log in to Claude"}
            </Button>
            {status === "error" && (
              <Button variant="ghost" disabled={busy} onClick={start}>
                Retry
              </Button>
            )}
          </div>
        ) : (
          <>
            <Callout tone="info">
              A Claude sign-in window should have opened. Authorize there, copy the code
              Claude shows you, and paste it below. If the window didn&apos;t open (popups
              blocked), use the button.
            </Callout>
            <div className="hstack" style={{ gap: 10, flexWrap: "wrap" }}>
              <Button
                variant="secondary"
                disabled={!url}
                onClick={() => {
                  if (url) popupRef.current = openLoginPopup(url);
                }}
              >
                Open Claude sign-in window ↗
              </Button>
              {url && (
                <a className="btn btn-ghost" href={url} target="_blank" rel="noopener noreferrer">
                  Open in a new tab
                </a>
              )}
              <Button variant="ghost" disabled={busy} onClick={start}>
                Restart
              </Button>
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
