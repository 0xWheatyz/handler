import React, { useMemo, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { radius, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { Select } from "../components/Select";
import { TabBar } from "../components/TabBar";
import { TextField } from "../components/TextField";
import { Card, Divider, Mono, SectionLabel } from "../components/primitives";
import { useAppState, type BadgeTone } from "../state/AppState";
import { timeAgo } from "../api/format";
import type { MemoryNote } from "../api/client";

/**
 * Memory — the agent-memory note graph (the web dashboard's Memory page).
 * Notes are the distilled facts/decisions/gotchas/runbooks agents leave for
 * each other; tapping a note expands its body, tags, and links. Operators can
 * author and delete notes here too (admin-gated server-side — notes feed every
 * future agent's context); link editing stays on the web dashboard's graph UI.
 */

const KIND_FILTERS = ["all", "fact", "decision", "gotcha", "runbook"];

const KIND_TONES: Record<string, BadgeTone> = {
  fact: "neutral",
  decision: "positive",
  gotcha: "danger",
  runbook: "warning",
};

export function MemoryScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { client, memory, memoryError, reloadMemory, projects } = useAppState();

  const [kind, setKind] = useState("all");
  const [openId, setOpenId] = useState<number | null>(null);

  // New-note form (POST /memory/notes; admin-gated server-side).
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [noteKind, setNoteKind] = useState("fact");
  const [project, setProject] = useState("");
  const [tags, setTags] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function createNote() {
    if (!client) return;
    if (!title.trim() || !body.trim()) {
      setFormError("A title and a body are both required.");
      return;
    }
    setFormError(null);
    setBusy(true);
    try {
      const tagList = tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await client.api("/memory/notes", {
        body: {
          title: title.trim(),
          body: body.trim(),
          kind: noteKind,
          project_id: project || null,
          ...(tagList.length > 0 ? { tags: tagList } : {}),
        },
      });
      setTitle("");
      setTags("");
      setBody("");
      setShowForm(false);
      reloadMemory();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Couldn't save the note.");
    } finally {
      setBusy(false);
    }
  }

  function confirmDeleteNote(n: MemoryNote) {
    Alert.alert(
      "Delete note?",
      `Remove "${n.title}" and its links. Future agents stop seeing it.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            if (!client) return;
            client
              .api(`/memory/notes/${n.id}`, { method: "DELETE" })
              .then(() => {
                setOpenId(null);
                reloadMemory();
              })
              .catch((e) =>
                setFormError(e instanceof Error ? e.message : "Delete failed."),
              );
          },
        },
      ],
    );
  }

  const notes = useMemo(() => {
    const all = memory?.notes ?? [];
    const inKind = kind === "all" ? all : all.filter((n) => n.kind === kind);
    return [...inKind].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );
  }, [memory, kind]);

  const byId = useMemo(
    () => new Map((memory?.notes ?? []).map((n) => [n.id, n])),
    [memory],
  );

  /* Both directions of the graph for one note: outgoing "relation → title" and
   * incoming "title → relation". */
  const linksFor = (note: MemoryNote): { key: string; label: string }[] => {
    const links = memory?.links ?? [];
    const out: { key: string; label: string }[] = [];
    for (const l of links) {
      if (l.src_note_id === note.id) {
        out.push({ key: `o${l.id}`, label: `${l.relation} → ${noteTitle(byId, l.dst_note_id)}` });
      } else if (l.dst_note_id === note.id) {
        out.push({ key: `i${l.id}`, label: `${noteTitle(byId, l.src_note_id)} → ${l.relation}` });
      }
    }
    return out;
  };

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />

      <View style={styles.header}>
        <View style={styles.headRow}>
          <Text style={[text.h3, { color: colors.textHeading }]}>Memory</Text>
          <Button
            size="sm"
            variant={showForm ? "secondary" : "primary"}
            onPress={() => setShowForm((v) => !v)}
          >
            {showForm ? "Cancel" : "New"}
          </Button>
        </View>
        <Text style={[text.bodySm, { color: colors.textMuted, marginTop: 4 }]}>
          Notes agents distill for every future run.
        </Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filters}
        >
          {KIND_FILTERS.map((k) => (
            <Chip
              key={k}
              label={k === "all" ? "All" : k}
              selected={kind === k}
              onPress={() => setKind(k)}
            />
          ))}
        </ScrollView>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.body}
        showsVerticalScrollIndicator={false}
      >
        {showForm ? (
          <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
            <View>
              <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                Title
              </Text>
              <TextField
                value={title}
                onChangeText={setTitle}
                placeholder="One-line takeaway"
              />
            </View>
            <Select
              label="Kind"
              options={["fact", "decision", "gotcha", "runbook"]}
              value={noteKind}
              onChange={setNoteKind}
            />
            <Select
              label="Scope"
              options={[
                { value: "", label: "Global (all projects)" },
                ...projects.map((p) => ({ value: p.id, label: p.id })),
              ]}
              value={project}
              onChange={setProject}
            />
            <View>
              <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                Tags
              </Text>
              <TextField
                value={tags}
                onChangeText={setTags}
                placeholder="comma, separated (optional)"
                autoCapitalize="none"
              />
            </View>
            <View>
              <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                Body
              </Text>
              <TextField
                value={body}
                onChangeText={setBody}
                placeholder="What should future agents know?"
                multiline
                height={100}
              />
            </View>
            <Button
              size="lg"
              style={{ width: "100%" }}
              onPress={busy ? undefined : createNote}
            >
              {busy ? "Saving…" : "Save note"}
            </Button>
          </Card>
        ) : null}

        {formError ? (
          <View
            style={[
              styles.notice,
              { backgroundColor: colors.dangerTint, borderColor: colors.danger },
            ]}
          >
            <Text style={[text.bodySm, { color: colors.danger }]}>{formError}</Text>
          </View>
        ) : null}

        {memoryError ? (
          <Text style={[text.bodySm, { color: colors.danger }]}>{memoryError}</Text>
        ) : memory === null ? (
          <Text style={[text.bodySm, { color: colors.textMuted }]}>Loading…</Text>
        ) : notes.length === 0 ? (
          <Text style={[text.bodySm, { color: colors.textMuted }]}>
            {kind === "all" ? "No notes yet." : `No ${kind} notes yet.`}
          </Text>
        ) : (
          <>
            <SectionLabel style={{ marginBottom: 8 }}>
              {`${notes.length} note${notes.length === 1 ? "" : "s"}`}
            </SectionLabel>
            <Card>
              {notes.map((n, i) => {
                const open = openId === n.id;
                const links = open ? linksFor(n) : [];
                return (
                  <View key={n.id}>
                    {i > 0 && <Divider />}
                    <Pressable
                      style={styles.row}
                      onPress={() => setOpenId(open ? null : n.id)}
                    >
                      <View style={styles.titleRow}>
                        <Badge tone={KIND_TONES[n.kind] ?? "neutral"}>{n.kind}</Badge>
                        <Text
                          numberOfLines={open ? undefined : 1}
                          style={[text.bodySm, { color: colors.textHeading, flex: 1 }]}
                        >
                          {n.title}
                        </Text>
                      </View>
                      <Text style={[text.caption, { color: colors.textMuted, marginTop: 4 }]}>
                        {n.project_id ?? "global"} · updated {timeAgo(n.updated_at)} ago
                      </Text>

                      {open ? (
                        <View style={{ marginTop: 10, gap: 8 }}>
                          <Text style={[text.bodySm, { color: colors.textBody }]}>
                            {n.body}
                          </Text>
                          {n.tags && n.tags.length > 0 ? (
                            <Mono style={{ fontSize: 12, color: colors.textMuted }}>
                              {n.tags.map((t) => `#${t}`).join("  ")}
                            </Mono>
                          ) : null}
                          {links.length > 0 ? (
                            <View style={{ gap: 4 }}>
                              <SectionLabel>Links</SectionLabel>
                              {links.map((l) => (
                                <Mono
                                  key={l.key}
                                  style={{ fontSize: 12, color: colors.textMuted }}
                                >
                                  {l.label}
                                </Mono>
                              ))}
                            </View>
                          ) : null}
                          <Button
                            size="sm"
                            variant="danger"
                            style={{ alignSelf: "flex-start" }}
                            onPress={() => confirmDeleteNote(n)}
                          >
                            Delete
                          </Button>
                        </View>
                      ) : null}
                    </Pressable>
                  </View>
                );
              })}
            </Card>
          </>
        )}
      </ScrollView>

      <TabBar active="memory" />
    </View>
  );
}

function noteTitle(byId: Map<number, MemoryNote>, id: number): string {
  return byId.get(id)?.title ?? `note #${id}`;
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  header: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 14 },
  headRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  filters: { flexDirection: "row", gap: 8, marginTop: 14, paddingRight: 20 },
  body: { paddingHorizontal: 20, paddingBottom: 24 },
  notice: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
    marginBottom: 16,
  },
  row: { paddingVertical: 12, paddingHorizontal: 16 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
});
