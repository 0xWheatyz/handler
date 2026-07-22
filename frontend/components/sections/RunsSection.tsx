/* Runs — the inbox: a flat list of every agent across every project on the left, the
 * selected agent's checkmark + log + answer/resume flow on the right. Maps the design's
 * "Runs" pane to Handler's agent / checkmark / log model. */
"use client";

import { useMemo, useState } from "react";
import { useDashboard } from "@/components/store";
import { Badge, Button, Callout, Stat, StatusBadge, Tabs, Textarea } from "@/components/ui";
import { fmtFull, shortSha, statusTone, timeAgo } from "@/lib/format";
import type { Agent, AgentEvent } from "@/lib/api";

const FILTERS = [
  { value: "all", label: "All" },
  { value: "needs", label: "Needs Input" },
  { value: "working", label: "Working" },
  { value: "done", label: "Done" },
  { value: "crashed", label: "Crashed" },
];

function matches(filter: string, status: string): boolean {
  if (filter === "all") return true;
  if (filter === "needs") return status === "paused_for_input";
  if (filter === "working") return status === "working" || status === "running";
  if (filter === "done") return status === "done" || status === "completed";
  if (filter === "crashed") return status === "crashed" || status === "blocked";
  return true;
}

export function RunsSection() {
  const s = useDashboard();
  const [filter, setFilter] = useState("all");

  const runs = useMemo(() => {
    const list = s.agents.filter((a) => matches(filter, a.status));
    return [...list].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  }, [s.agents, filter]);

  const selected = s.selectedRun;

  const needs = s.agents.filter((a) => a.status === "paused_for_input").length;
  const working = s.agents.filter((a) => a.status === "working" || a.status === "running").length;

  return (
    <div className="runs">
      <div className="runs-stats">
        <div className="stat-row">
          <div className="stat-cell">
            <Stat value={s.agents.length} label="Runs tracked" />
          </div>
          <div className="stat-cell">
            <Stat value={needs} label="Needs input" accent />
          </div>
          <div className="stat-cell">
            <Stat value={working} label="Working" />
          </div>
          <div className="stat-cell">
            <Stat value={s.projects.length} label="Repositories" />
          </div>
        </div>
      </div>
      <div className="split">
      <div className="split-list">
        <div className="split-list-head">
          <div className="section-title" style={{ fontSize: "var(--text-lg)" }}>
            Runs
          </div>
          <Tabs tabs={FILTERS} value={filter} onChange={setFilter} />
        </div>
        <div className="split-list-scroll">
          {runs.length === 0 && <Callout tone="info">No runs match this filter.</Callout>}
          {runs.map((a) => (
            <RunRow
              key={`${a.project_id}/${a.name}`}
              agent={a}
              selected={selected?.projectId === a.project_id && selected?.name === a.name}
              onSelect={() => s.selectRun(a.project_id, a.name)}
            />
          ))}
        </div>
      </div>

      <div className="split-detail">
        {selected ? <RunDetail /> : <RunEmpty />}
      </div>
      </div>
    </div>
  );
}

function RunRow({
  agent,
  selected,
  onSelect,
}: {
  agent: Agent;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button className={`run-row${selected ? " selected" : ""}`} onClick={onSelect}>
      <div className="run-row-top">
        <span className="run-project">{agent.project_id}</span>
        <span className="faint mono" style={{ fontSize: "var(--text-xs)" }}>
          {timeAgo(agent.created_at)}
        </span>
      </div>
      <div className="truncate muted" style={{ fontSize: "var(--text-sm)" }}>
        {agent.name}
        {agent.role ? ` · ${agent.role}` : ""}
      </div>
      <div className="hstack" style={{ gap: 8 }}>
        <StatusBadge status={agent.status} />
      </div>
    </button>
  );
}

function RunEmpty() {
  return (
    <div style={{ padding: "60px 32px", color: "var(--text-muted)" }}>
      Select a run to see its checkmark, log, and any open question.
    </div>
  );
}

function RunDetail() {
  const s = useDashboard();
  const run = s.selectedRun!;
  const agent = s.agents.find((a) => a.project_id === run.projectId && a.name === run.name);
  const cm = s.checkmark;

  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const isPaused = agent?.status === "paused_for_input";

  const doAnswer = async (resume: boolean) => {
    if (!answer.trim()) return;
    setBusy(true);
    const ok = await s.submitAnswer(answer.trim(), resume);
    setBusy(false);
    if (ok) setAnswer("");
  };

  return (
    <>
      <div
        style={{
          padding: "24px 28px",
          borderBottom: "1px solid var(--border-default)",
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <div className="hstack">
          <span style={{ color: "var(--accent)", fontWeight: "var(--fw-bold)", fontSize: "var(--text-xl)" }}>
            {run.projectId}
          </span>
          <span className="faint">/</span>
          <span style={{ color: "var(--text-heading)", fontWeight: "var(--fw-semibold)", fontSize: "var(--text-lg)" }}>
            {run.name}
          </span>
          <StatusBadge status={agent?.status} />
          {agent?.role && <Badge tone="info">{agent.role}</Badge>}
          <span className="spacer" />
          <Button size="sm" variant="secondary" onClick={() => s.killAgent(run.projectId, run.name)}>
            Kill
          </Button>
          <Button size="sm" variant="danger" onClick={() => s.deleteAgent(run.projectId, run.name)}>
            Delete row
          </Button>
        </div>
        <div className="mono faint" style={{ fontSize: "var(--text-xs)" }}>
          {agent?.working_dir ?? "—"} · created {fmtFull(agent?.created_at)}
        </div>
      </div>

      <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Checkmark */}
        <div>
          <div className="eyebrow" style={{ marginBottom: 10 }}>
            Checkmark
          </div>
          {s.checkmarkMissing && <Callout tone="info">No checkpoint recorded yet.</Callout>}
          {cm && !s.checkmarkMissing && (
            <dl className="kv">
              <dt>Status</dt>
              <dd>
                <StatusBadge status={cm.status} />
              </dd>
              <dt>Where it stopped</dt>
              <dd>{cm.where_it_stopped || "—"}</dd>
              <dt>Open question</dt>
              <dd>{cm.open_question || "—"}</dd>
              <dt>Next steps</dt>
              <dd>
                {cm.next_steps && cm.next_steps.length > 0 ? (
                  <ul>
                    {cm.next_steps.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ul>
                ) : (
                  "—"
                )}
              </dd>
              <dt>Tests</dt>
              <dd className="hstack">
                <Badge tone={statusTone(cm.tests_status)}>{cm.tests_status}</Badge>
                <span className="faint mono" style={{ fontSize: "var(--text-xs)" }}>
                  {cm.tested_at ? fmtFull(cm.tested_at) : ""}
                </span>
              </dd>
              <dt>Build</dt>
              <dd className="hstack">
                <Badge tone={statusTone(cm.build_status)}>{cm.build_status}</Badge>
                <span className="faint mono" style={{ fontSize: "var(--text-xs)" }}>
                  {cm.built_at ? fmtFull(cm.built_at) : ""}
                </span>
              </dd>
              <dt>Checkpoint at</dt>
              <dd className="faint">{fmtFull(cm.checkpoint_at)}</dd>
            </dl>
          )}
        </div>

        {/* Answer / resume */}
        {isPaused && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="eyebrow">Answer this question</div>
            <Callout tone="danger">{cm?.open_question || "(no question text on the checkmark)"}</Callout>
            <Textarea value={answer} onChange={setAnswer} rows={3} placeholder="Your answer…" />
            <div className="hstack">
              <Button variant="secondary" disabled={busy || !answer.trim()} onClick={() => doAnswer(false)}>
                Answer
              </Button>
              <Button variant="primary" disabled={busy || !answer.trim()} onClick={() => doAnswer(true)}>
                Answer &amp; Resume
              </Button>
            </div>
          </div>
        )}

        {/* Headless run event stream (empty for legacy tmux agents) */}
        {agent?.session_id && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="eyebrow">
              Run events
              {agent.worker_id ? (
                <span className="faint mono" style={{ fontSize: "var(--text-xs)", marginLeft: 8 }}>
                  on {agent.worker_id}
                </span>
              ) : null}
            </div>
            {s.events.length === 0 ? (
              <div className="empty">No events yet.</div>
            ) : (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  maxHeight: 420,
                  overflow: "auto",
                  padding: "10px 12px",
                  background: "var(--surface-2, rgba(0,0,0,0.25))",
                  borderRadius: 6,
                }}
              >
                {s.events.map((e) => (
                  <EventLine key={e.id} e={e} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Log */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="eyebrow">Log · newest first</div>
          {s.log.length === 0 ? (
            <div className="empty">No log entries.</div>
          ) : (
            <div className="table-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Status</th>
                    <th>Summary</th>
                    <th>Q / A</th>
                    <th>Push</th>
                    <th>CI</th>
                  </tr>
                </thead>
                <tbody>
                  {s.log.map((e) => (
                    <tr key={e.id}>
                      <td className="faint nowrap">{fmtFull(e.created_at)}</td>
                      <td>
                        <StatusBadge status={e.status} />
                      </td>
                      <td>{e.summary || "—"}</td>
                      <td>
                        {e.question && (
                          <div>
                            <strong>Q:</strong> {e.question}
                          </div>
                        )}
                        {e.answer && (
                          <div>
                            <strong>A:</strong> {e.answer}
                          </div>
                        )}
                        {!e.question && !e.answer && "—"}
                      </td>
                      <td className="mono">{shortSha(e.push_sha)}</td>
                      <td>
                        <Badge tone={statusTone(e.ci_status)}>{e.ci_status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pager">
            <Button size="sm" variant="ghost" disabled={s.logOffset === 0} onClick={() => s.pageLog(-1)}>
              ‹ Newer
            </Button>
            <span className="faint mono" style={{ fontSize: "var(--text-xs)" }}>
              offset {s.logOffset}
            </span>
            <Button size="sm" variant="ghost" disabled={s.log.length < 100} onClick={() => s.pageLog(1)}>
              Older ›
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}

/* One stream-json event, rendered by type: assistant text as prose, tool calls as chips,
 * the result as a cost/turns footer, worker notices as callouts, raw lines verbatim. */
function EventLine({ e }: { e: AgentEvent }) {
  const p = (e.payload ?? {}) as Record<string, any>;
  const xs = { fontSize: "var(--text-xs)" } as const;

  if (e.type === "system") {
    return (
      <div className="faint mono" style={xs}>
        ▸ session {p.subtype ?? "event"}
        {p.session_id ? ` · ${String(p.session_id).slice(0, 8)}` : ""}
        {Array.isArray(p.tools) ? ` · ${p.tools.length} tools` : ""}
      </div>
    );
  }
  if (e.type === "assistant") {
    const content = p.message?.content;
    const blocks: any[] = Array.isArray(content) ? content : [];
    const text = blocks
      .filter((b) => b?.type === "text" && b.text)
      .map((b) => b.text)
      .join("\n");
    const tools = blocks.filter((b) => b?.type === "tool_use");
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {text && (
          <div style={{ fontSize: "var(--text-sm)", whiteSpace: "pre-wrap" }}>{text}</div>
        )}
        {tools.length > 0 && (
          <div className="hstack" style={{ gap: 6, flexWrap: "wrap" }}>
            {tools.map((t, i) => (
              <Badge key={i} tone="info">
                {t.name}
                {t.input ? `: ${oneLine(t.input)}` : ""}
              </Badge>
            ))}
          </div>
        )}
      </div>
    );
  }
  if (e.type === "result") {
    const err = Boolean(p.is_error);
    return (
      <div className="hstack" style={{ gap: 8, flexWrap: "wrap" }}>
        <Badge tone={err ? "danger" : "success"}>{err ? "run errored" : "run finished"}</Badge>
        <span className="faint mono" style={xs}>
          {p.num_turns != null ? `${p.num_turns} turns` : ""}
          {p.total_cost_usd != null ? ` · $${Number(p.total_cost_usd).toFixed(4)}` : ""}
        </span>
        {typeof p.result === "string" && p.result && (
          <span className="muted" style={{ ...xs, whiteSpace: "pre-wrap", width: "100%" }}>
            {p.result}
          </span>
        )}
      </div>
    );
  }
  if (e.type === "worker") {
    return (
      <Callout tone="danger">
        {p.notice ?? "runner notice"}
        {p.stderr_tail ? (
          <pre className="mono" style={{ ...xs, margin: "6px 0 0", whiteSpace: "pre-wrap" }}>
            {p.stderr_tail}
          </pre>
        ) : null}
      </Callout>
    );
  }
  if (e.type === "raw") {
    return (
      <div className="faint mono" style={{ ...xs, whiteSpace: "pre-wrap" }}>
        {typeof p.line === "string" ? p.line.trimEnd() : JSON.stringify(p)}
      </div>
    );
  }
  // user (tool results) and anything future: a quiet one-liner, nothing lost, no noise.
  return (
    <div className="faint mono" style={xs}>
      ▸ {e.type}
    </div>
  );
}

/* Compact single-line preview of a tool_use input object. */
function oneLine(input: unknown): string {
  const s =
    typeof input === "string"
      ? input
      : (input as Record<string, unknown>)?.command
        ? String((input as Record<string, unknown>).command)
        : JSON.stringify(input);
  return s.length > 80 ? `${s.slice(0, 77)}…` : s;
}
