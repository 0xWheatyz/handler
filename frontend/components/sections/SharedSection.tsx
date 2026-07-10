/* Shared — the cross-project global feed and the shared key/value context store.
 * Writing a context key needs the higher-trust shared-write token. */
"use client";

import { useState } from "react";
import { useDashboard } from "@/components/store";
import { Button, Card, Input, StatusBadge } from "@/components/ui";
import { fmtFull } from "@/lib/format";

export function SharedSection() {
  const s = useDashboard();
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  const set = async () => {
    if (!key.trim() || !value.trim()) return;
    const ok = await s.setSharedKey(key.trim(), value.trim());
    if (ok) {
      setKey("");
      setValue("");
    }
  };

  return (
    <>
      <div className="section-head">
        <div className="section-title">Shared</div>
        <div className="section-desc">The cross-project global feed and shared facts.</div>
      </div>
      <div className="section-body">
        <div>
          <div className="eyebrow" style={{ marginBottom: 10 }}>
            Global feed
          </div>
          {s.shared.log.length === 0 ? (
            <div className="empty">No global log entries.</div>
          ) : (
            <div className="table-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Agent</th>
                    <th>Status</th>
                    <th>Summary</th>
                    <th>CI</th>
                  </tr>
                </thead>
                <tbody>
                  {s.shared.log.map((e) => (
                    <tr key={e.id}>
                      <td className="faint nowrap">{fmtFull(e.created_at)}</td>
                      <td className="mono">{e.agent_id}</td>
                      <td>
                        <StatusBadge status={e.status} />
                      </td>
                      <td>{e.summary || "—"}</td>
                      <td>
                        <StatusBadge status={e.ci_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <Card>
          <div className="card-head" style={{ marginBottom: 14 }}>
            <span className="card-title" style={{ fontSize: "var(--text-md)", color: "var(--text-heading)" }}>
              Set a shared key
            </span>
          </div>
          <div className="form-grid">
            <Input label="Key" value={key} onChange={setKey} placeholder="key" />
            <Input label="Value" value={value} onChange={setValue} placeholder="value" />
          </div>
          <p className="faint" style={{ fontSize: "var(--text-xs)", margin: "10px 0 0" }}>
            Requires the shared-context write token (or admin/global if unset).
          </p>
          <div className="hstack mt14">
            <Button variant="primary" disabled={!key.trim() || !value.trim()} onClick={set}>
              Set
            </Button>
          </div>
        </Card>

        {s.shared.context.length > 0 && (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Value</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {s.shared.context.map((c) => (
                  <tr key={c.key}>
                    <td className="mono">{c.key}</td>
                    <td>{c.value}</td>
                    <td className="faint nowrap">{fmtFull(c.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
