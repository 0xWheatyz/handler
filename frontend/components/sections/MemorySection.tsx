/* Memory — the distilled knowledge agents leave behind, drawn as the web of notes.
 * Nodes are notes (colored by kind), edges are the links agents/operators asserted
 * between them. The layout is a small hand-rolled force simulation — deliberately no
 * chart library, matching the rest of the hand-rolled UI. Reads come from
 * GET /memory/graph via the store; writes are direct admin-token calls. */
"use client";

import { useMemo, useState } from "react";
import type { MemoryLink, MemoryNote, NoteKind } from "@/lib/api";
import { useDashboard, type MemoryNoteBody } from "@/components/store";
import { Badge, Button, Card, Input, Select, Textarea } from "@/components/ui";
import { fmtFull } from "@/lib/format";

const KIND_COLORS: Record<string, string> = {
  fact: "var(--lw-blue-400)",
  decision: "var(--lw-indigo-400)",
  gotcha: "var(--lw-warning-fg)",
  runbook: "var(--lw-success-fg)",
};
const KINDS: NoteKind[] = ["fact", "decision", "gotcha", "runbook"];

const W = 900;
const H = 560;

interface Pos {
  x: number;
  y: number;
}

/* Deterministic force layout: seed on a circle (stable order = stable picture), then
 * relax with link springs, pairwise repulsion, and a centering pull. Runs to a fixed
 * iteration budget synchronously — the graphs here are distilled notes, not big data. */
function computeLayout(notes: MemoryNote[], links: MemoryLink[]): Map<number, Pos> {
  const pos = new Map<number, Pos>();
  const n = notes.length;
  if (n === 0) return pos;
  const cx = W / 2;
  const cy = H / 2;
  const seedR = Math.min(W, H) / 2 - 80;
  notes.forEach((note, i) => {
    const a = (2 * Math.PI * i) / n;
    pos.set(note.id, { x: cx + seedR * Math.cos(a), y: cy + seedR * Math.sin(a) });
  });
  const ids = notes.map((note) => note.id);
  const iterations = n > 150 ? 80 : 250;
  const springLen = 120;
  for (let it = 0; it < iterations; it++) {
    const temp = 1 - it / iterations; // cool down
    const force = new Map<number, Pos>(ids.map((id) => [id, { x: 0, y: 0 }]));
    // Pairwise repulsion.
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = pos.get(ids[i])!;
        const b = pos.get(ids[j])!;
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        const d2 = Math.max(dx * dx + dy * dy, 1);
        const d = Math.sqrt(d2);
        const rep = 2600 / d2;
        dx = (dx / d) * rep;
        dy = (dy / d) * rep;
        const fa = force.get(ids[i])!;
        const fb = force.get(ids[j])!;
        fa.x += dx;
        fa.y += dy;
        fb.x -= dx;
        fb.y -= dy;
      }
    }
    // Link springs.
    for (const ln of links) {
      const a = pos.get(ln.src_note_id);
      const b = pos.get(ln.dst_note_id);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const pull = (d - springLen) * 0.02;
      const fa = force.get(ln.src_note_id)!;
      const fb = force.get(ln.dst_note_id)!;
      fa.x += (dx / d) * pull;
      fa.y += (dy / d) * pull;
      fb.x -= (dx / d) * pull;
      fb.y -= (dy / d) * pull;
    }
    // Centering pull + apply.
    for (const id of ids) {
      const p = pos.get(id)!;
      const f = force.get(id)!;
      f.x += (cx - p.x) * 0.005;
      f.y += (cy - p.y) * 0.005;
      p.x += Math.max(-12, Math.min(12, f.x)) * temp;
      p.y += Math.max(-12, Math.min(12, f.y)) * temp;
      p.x = Math.max(30, Math.min(W - 30, p.x));
      p.y = Math.max(24, Math.min(H - 24, p.y));
    }
  }
  return pos;
}

const emptyForm: MemoryNoteBody = { title: "", body: "", kind: "fact", project_id: "", tags: [] };

export function MemorySection() {
  const s = useDashboard();
  const [projectFilter, setProjectFilter] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [hoverId, setHoverId] = useState<number | null>(null);
  const [form, setForm] = useState<MemoryNoteBody>(emptyForm);
  const [tagsText, setTagsText] = useState("");
  const [editing, setEditing] = useState(false);
  const [linkDst, setLinkDst] = useState("");
  const [linkRelation, setLinkRelation] = useState("relates_to");

  const notes = useMemo(() => {
    if (!projectFilter) return s.memory.notes;
    if (projectFilter === "global") return s.memory.notes.filter((n) => !n.project_id);
    return s.memory.notes.filter(
      (n) => n.project_id === projectFilter || !n.project_id,
    );
  }, [s.memory.notes, projectFilter]);

  const links = useMemo(() => {
    const inScope = new Set(notes.map((n) => n.id));
    return s.memory.links.filter(
      (ln) => inScope.has(ln.src_note_id) && inScope.has(ln.dst_note_id),
    );
  }, [s.memory.links, notes]);

  /* Recompute only when the graph's shape actually changes, not on every poll. */
  const layoutKey = useMemo(
    () =>
      notes.map((n) => n.id).join(",") +
      "|" +
      links.map((ln) => ln.id).join(","),
    [notes, links],
  );
  const layout = useMemo(
    () => computeLayout(notes, links),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [layoutKey],
  );

  const degree = useMemo(() => {
    const d = new Map<number, number>();
    for (const ln of links) {
      d.set(ln.src_note_id, (d.get(ln.src_note_id) ?? 0) + 1);
      d.set(ln.dst_note_id, (d.get(ln.dst_note_id) ?? 0) + 1);
    }
    return d;
  }, [links]);

  const selected = notes.find((n) => n.id === selectedId) ?? null;
  const focusId = hoverId ?? selectedId;
  const neighborhood = useMemo(() => {
    if (focusId == null) return null;
    const set = new Set<number>([focusId]);
    for (const ln of links) {
      if (ln.src_note_id === focusId) set.add(ln.dst_note_id);
      if (ln.dst_note_id === focusId) set.add(ln.src_note_id);
    }
    return set;
  }, [focusId, links]);

  const selectedLinks = useMemo(
    () =>
      selected
        ? links.filter(
            (ln) => ln.src_note_id === selected.id || ln.dst_note_id === selected.id,
          )
        : [],
    [selected, links],
  );

  const titleOf = (id: number) => s.memory.notes.find((n) => n.id === id)?.title ?? `#${id}`;

  const parseTags = (text: string) =>
    text
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

  const saveNote = async () => {
    const body = { ...form, tags: parseTags(tagsText) };
    const ok =
      editing && selected
        ? await s.updateMemoryNote(selected.id, body)
        : await s.createMemoryNote(body);
    if (ok) {
      setForm(emptyForm);
      setTagsText("");
      setEditing(false);
    }
  };

  const startEdit = () => {
    if (!selected) return;
    setForm({
      title: selected.title,
      body: selected.body,
      kind: (KINDS.includes(selected.kind as NoteKind) ? selected.kind : "fact") as NoteKind,
      project_id: selected.project_id ?? "",
      tags: selected.tags ?? [],
    });
    setTagsText((selected.tags ?? []).join(", "));
    setEditing(true);
  };

  const addLink = async () => {
    if (!selected || !linkDst) return;
    const ok = await s.createMemoryLink(selected.id, Number(linkDst), linkRelation.trim());
    if (ok) setLinkDst("");
  };

  const projectOptions = [
    { value: "", label: "All projects" },
    { value: "global", label: "Global only" },
    ...s.projects.map((p) => ({ value: p.id, label: p.id })),
  ];

  return (
    <>
      <div className="section-head">
        <div className="section-title">Memory</div>
        <div className="section-desc">
          The web of notes agents and operators leave behind — facts, decisions, gotchas,
          runbooks — and how they connect.
        </div>
      </div>
      <div className="section-body">
        <div className="hstack wrap" style={{ alignItems: "flex-end", gap: 12 }}>
          <div style={{ width: 220 }}>
            <Select
              label="Scope"
              value={projectFilter}
              onChange={setProjectFilter}
              options={projectOptions}
            />
          </div>
          <div className="hstack" style={{ gap: 8, paddingBottom: 6 }}>
            {KINDS.map((k) => (
              <span key={k} className="hstack" style={{ gap: 5, alignItems: "center" }}>
                <span
                  style={{
                    width: 9,
                    height: 9,
                    borderRadius: "50%",
                    background: KIND_COLORS[k],
                    display: "inline-block",
                  }}
                />
                <span className="faint" style={{ fontSize: "var(--text-xs)" }}>
                  {k}
                </span>
              </span>
            ))}
          </div>
        </div>

        {notes.length === 0 ? (
          <div className="empty">
            No memory notes yet. Agents write them with the handler-memory MCP tools
            (memory_save / memory_link); you can add one below.
          </div>
        ) : (
          <Card>
            <svg
              viewBox={`0 0 ${W} ${H}`}
              style={{ width: "100%", height: "auto", display: "block" }}
              role="img"
              aria-label="Graph of memory notes and their links"
            >
              {links.map((ln) => {
                const a = layout.get(ln.src_note_id);
                const b = layout.get(ln.dst_note_id);
                if (!a || !b) return null;
                const focused =
                  focusId != null &&
                  (ln.src_note_id === focusId || ln.dst_note_id === focusId);
                return (
                  <g key={ln.id}>
                    <line
                      x1={a.x}
                      y1={a.y}
                      x2={b.x}
                      y2={b.y}
                      stroke={focused ? "var(--lw-blue-300)" : "var(--border-strong)"}
                      strokeWidth={focused ? 1.6 : 1}
                      opacity={neighborhood && !focused ? 0.25 : 0.8}
                    />
                    {focused && (
                      <text
                        x={(a.x + b.x) / 2}
                        y={(a.y + b.y) / 2 - 4}
                        textAnchor="middle"
                        fill="var(--text-faint)"
                        fontSize={10}
                      >
                        {ln.relation}
                      </text>
                    )}
                  </g>
                );
              })}
              {notes.map((n) => {
                const p = layout.get(n.id);
                if (!p) return null;
                const r = 6 + Math.min(degree.get(n.id) ?? 0, 6);
                const dimmed = neighborhood != null && !neighborhood.has(n.id);
                const isSelected = n.id === selectedId;
                return (
                  <g
                    key={n.id}
                    transform={`translate(${p.x},${p.y})`}
                    style={{ cursor: "pointer" }}
                    opacity={dimmed ? 0.3 : 1}
                    onMouseEnter={() => setHoverId(n.id)}
                    onMouseLeave={() => setHoverId(null)}
                    onClick={() => {
                      setSelectedId(n.id === selectedId ? null : n.id);
                      setEditing(false);
                    }}
                  >
                    <circle
                      r={r}
                      fill={KIND_COLORS[n.kind] ?? "var(--lw-neutral-fg)"}
                      stroke={isSelected ? "var(--lw-white)" : "var(--surface-page)"}
                      strokeWidth={isSelected ? 2 : 1}
                    />
                    <text
                      y={r + 12}
                      textAnchor="middle"
                      fill={dimmed ? "var(--text-faint)" : "var(--text-muted)"}
                      fontSize={10.5}
                    >
                      {n.title.length > 24 ? n.title.slice(0, 24) + "…" : n.title}
                    </text>
                  </g>
                );
              })}
            </svg>
          </Card>
        )}

        {selected && (
          <Card>
            <div className="card-head" style={{ marginBottom: 10 }}>
              <span
                className="card-title"
                style={{ fontSize: "var(--text-md)", color: "var(--text-heading)" }}
              >
                {selected.title}
              </span>
              <span className="hstack" style={{ gap: 8 }}>
                <Badge>{selected.kind}</Badge>
                <Badge>{selected.project_id ?? "global"}</Badge>
              </span>
            </div>
            <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{selected.body}</p>
            <p className="faint" style={{ fontSize: "var(--text-xs)", margin: "10px 0 0" }}>
              {selected.agent_id != null ? `written by agent ${selected.agent_id}` : "operator-authored"}
              {" · updated "}
              {fmtFull(selected.updated_at)}
              {selected.tags?.length ? ` · tags: ${selected.tags.join(", ")}` : ""}
            </p>

            {selectedLinks.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div className="eyebrow" style={{ marginBottom: 6 }}>
                  Links
                </div>
                {selectedLinks.map((ln) => {
                  const otherId =
                    ln.src_note_id === selected.id ? ln.dst_note_id : ln.src_note_id;
                  const outgoing = ln.src_note_id === selected.id;
                  return (
                    <div key={ln.id} className="hstack" style={{ gap: 8, marginBottom: 4 }}>
                      <span className="faint" style={{ fontSize: "var(--text-xs)" }}>
                        {outgoing ? `${ln.relation} →` : `← ${ln.relation}`}
                      </span>
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          setSelectedId(otherId);
                        }}
                      >
                        {titleOf(otherId)}
                      </a>
                      <Button size="sm" variant="ghost" onClick={() => s.deleteMemoryLink(ln.id)}>
                        remove
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="hstack wrap mt14" style={{ gap: 8, alignItems: "flex-end" }}>
              <div style={{ width: 260 }}>
                <Select
                  label="Link to"
                  value={linkDst}
                  onChange={setLinkDst}
                  options={[
                    { value: "", label: "— pick a note —" },
                    ...notes
                      .filter((n) => n.id !== selected.id)
                      .map((n) => ({ value: String(n.id), label: n.title })),
                  ]}
                />
              </div>
              <div style={{ width: 160 }}>
                <Input label="Relation" value={linkRelation} onChange={setLinkRelation} />
              </div>
              <Button disabled={!linkDst} onClick={addLink}>
                Link
              </Button>
              <Button variant="secondary" onClick={startEdit}>
                Edit
              </Button>
              <Button
                variant="danger"
                onClick={async () => {
                  await s.deleteMemoryNote(selected.id);
                  setSelectedId(null);
                }}
              >
                Delete
              </Button>
            </div>
          </Card>
        )}

        <Card>
          <div className="card-head" style={{ marginBottom: 14 }}>
            <span
              className="card-title"
              style={{ fontSize: "var(--text-md)", color: "var(--text-heading)" }}
            >
              {editing && selected ? `Edit note: ${selected.title}` : "New note"}
            </span>
          </div>
          <div className="form-grid">
            <Input
              label="Title"
              value={form.title}
              onChange={(v) => setForm((f) => ({ ...f, title: v }))}
              placeholder="Short, searchable headline"
            />
            <Select
              label="Kind"
              value={form.kind}
              onChange={(v) => setForm((f) => ({ ...f, kind: v as NoteKind }))}
              options={KINDS.map((k) => ({ value: k, label: k }))}
            />
            <Select
              label="Project"
              value={form.project_id}
              onChange={(v) => setForm((f) => ({ ...f, project_id: v }))}
              options={[
                { value: "", label: "Global" },
                ...s.projects.map((p) => ({ value: p.id, label: p.id })),
              ]}
            />
            <Input
              label="Tags (comma-separated)"
              value={tagsText}
              onChange={setTagsText}
              placeholder="auth, deploy"
            />
          </div>
          <Textarea
            label="Body"
            value={form.body}
            onChange={(v) => setForm((f) => ({ ...f, body: v }))}
            rows={5}
            placeholder="The knowledge itself — written for a reader with no context."
          />
          <div className="hstack mt14" style={{ gap: 8 }}>
            <Button
              variant="primary"
              disabled={!form.title.trim() || !form.body.trim()}
              onClick={saveNote}
            >
              {editing ? "Save changes" : "Add note"}
            </Button>
            {editing && (
              <Button
                variant="ghost"
                onClick={() => {
                  setEditing(false);
                  setForm(emptyForm);
                  setTagsText("");
                }}
              >
                Cancel
              </Button>
            )}
          </div>
          <p className="faint" style={{ fontSize: "var(--text-xs)", margin: "10px 0 0" }}>
            Writes require the admin token. Agents add notes themselves through the bundled
            handler-memory MCP server.
          </p>
        </Card>
      </div>
    </>
  );
}
