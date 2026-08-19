import React, { useEffect, useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { radius, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import { Switch } from "../components/Switch";
import { TabBar } from "../components/TabBar";
import { TextField } from "../components/TextField";
import { Card, Divider, Mono, SectionLabel } from "../components/primitives";
import { useAppState } from "../state/AppState";
import { timeAgo } from "../api/format";
import type { Schedule } from "../api/client";

/**
 * Schedules — recurring agent spawns, the mobile counterpart of the web
 * dashboard's Schedules page. Every interval the worker starts a fresh,
 * stateless agent named <prefix>-<timestamp> with the stored prompt.
 */

const ROLE_OPTIONS = [
  { value: "", label: "Role — none" },
  { value: "scout", label: "scout" },
  { value: "planner", label: "planner" },
  { value: "junior", label: "junior" },
  { value: "senior", label: "senior" },
  { value: "deploy", label: "deploy" },
];

const INTERVAL_OPTIONS = [
  { value: "900", label: "every 15 minutes" },
  { value: "1800", label: "every 30 minutes" },
  { value: "3600", label: "every hour" },
  { value: "21600", label: "every 6 hours" },
  { value: "86400", label: "every day" },
  { value: "604800", label: "every week" },
];

function intervalLabel(seconds: number): string {
  const opt = INTERVAL_OPTIONS.find((o) => Number(o.value) === seconds);
  if (opt) return opt.label;
  if (seconds % 3600 === 0) return `every ${seconds / 3600}h`;
  if (seconds % 60 === 0) return `every ${seconds / 60}m`;
  return `every ${seconds}s`;
}

export function SchedulesScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const {
    projects,
    models,
    schedules,
    createSchedule,
    toggleSchedule,
    deleteSchedule,
  } = useAppState();

  const projectIds = projects.map((p) => p.id);
  const [showForm, setShowForm] = useState(false);
  const [project, setProject] = useState("");
  const [prefix, setPrefix] = useState("");
  const [task, setTask] = useState("");
  const [interval, setIntervalStr] = useState("3600");
  const [role, setRole] = useState("");
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (projectIds.length > 0 && !projectIds.includes(project)) {
      setProject(projectIds[0]);
    }
  }, [projectIds, project]);

  const modelOptions = [
    { value: "", label: "Claude (subscription)" },
    ...models
      .filter((m) => m.enabled)
      .map((m) => ({ value: String(m.id), label: `${m.name} (${m.model})` })),
  ];
  const modelName = (id: number | null | undefined) =>
    id == null ? null : models.find((m) => m.id === id)?.name ?? `#${id}`;

  async function create() {
    if (!project || !prefix.trim() || !task.trim()) {
      setError("Project, name prefix, and prompt are all required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await createSchedule(project, {
        name_prefix: prefix.trim(),
        task: task.trim(),
        interval_seconds: Number(interval),
        role: role || null,
        model_id: model ? Number(model) : null,
      });
      setPrefix("");
      setTask("");
      setShowForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t create the schedule.");
    } finally {
      setBusy(false);
    }
  }

  function confirmDelete(sc: Schedule) {
    Alert.alert(
      "Delete schedule?",
      `Stop spawning ${sc.name_prefix}-* runs in ${sc.project_id}. This can’t be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            deleteSchedule(sc.id).catch((e) =>
              setError(e instanceof Error ? e.message : "Delete failed."),
            );
          },
        },
      ],
    );
  }

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.headRow}>
          <Text style={[text.h3, { color: colors.textHeading }]}>Schedules</Text>
          <Button
            size="sm"
            variant={showForm ? "secondary" : "primary"}
            onPress={() => setShowForm((v) => !v)}
          >
            {showForm ? "Cancel" : "New"}
          </Button>
        </View>
        <Text style={[text.bodySm, { color: colors.textMuted, marginBottom: 16 }]}>
          Spawn a fresh agent on an interval. Each run is stateless — keep
          continuity in a file the prompt reads and overwrites.
        </Text>

        {showForm ? (
          <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
            {projectIds.length > 0 ? (
              <Select
                label="Project"
                options={projectIds}
                value={project || projectIds[0]}
                onChange={setProject}
              />
            ) : (
              <Text style={[text.bodySm, { color: colors.textMuted }]}>
                No projects registered yet.
              </Text>
            )}
            <View>
              <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                Name prefix
              </Text>
              <TextField
                value={prefix}
                onChangeText={setPrefix}
                placeholder="nightly"
                autoCapitalize="none"
                autoCorrect={false}
              />
              <Text style={[text.caption, { color: colors.textMuted, marginTop: 6 }]}>
                Runs are named {prefix.trim() || "prefix"}-YYYYMMDD-HHMMSS.
              </Text>
            </View>
            <Select
              label="Interval"
              options={INTERVAL_OPTIONS}
              value={interval}
              onChange={setIntervalStr}
            />
            <Select label="Role" options={ROLE_OPTIONS} value={role} onChange={setRole} />
            {modelOptions.length > 1 ? (
              <Select
                label="Model"
                options={modelOptions}
                value={model}
                onChange={setModel}
              />
            ) : null}
            <View>
              <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                Prompt
              </Text>
              <TextField
                value={task}
                onChangeText={setTask}
                placeholder="What should every run do?"
                multiline
                height={100}
              />
            </View>
            <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : create}>
              {busy ? "Creating…" : "Create schedule"}
            </Button>
          </Card>
        ) : null}

        {error ? (
          <View
            style={[
              styles.notice,
              { backgroundColor: colors.dangerTint, borderColor: colors.danger },
            ]}
          >
            <Text style={[text.bodySm, { color: colors.danger }]}>{error}</Text>
          </View>
        ) : null}

        <SectionLabel style={{ marginBottom: 8 }}>
          {`${schedules.length} schedule${schedules.length === 1 ? "" : "s"}`}
        </SectionLabel>

        {schedules.length === 0 ? (
          <Text style={[text.bodySm, { color: colors.textMuted }]}>
            No schedules yet.
          </Text>
        ) : (
          <Card>
            {schedules.map((sc, i) => (
              <View key={sc.id}>
                {i > 0 && <Divider />}
                <View style={styles.row}>
                  <View style={{ flex: 1, gap: 4 }}>
                    <View style={styles.titleRow}>
                      <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                        {sc.name_prefix}
                      </Mono>
                      {sc.role ? <Badge tone="neutral">{sc.role}</Badge> : null}
                      {sc.model_id != null ? (
                        <Badge tone="warning">{modelName(sc.model_id) ?? ""}</Badge>
                      ) : null}
                    </View>
                    <Text style={[text.caption, { color: colors.textMuted }]}>
                      {sc.project_id} · {intervalLabel(sc.interval_seconds)}
                    </Text>
                    <Text
                      numberOfLines={2}
                      style={[text.caption, { color: colors.textMuted }]}
                    >
                      {sc.task}
                    </Text>
                    <Text style={[text.caption, { color: colors.textMuted }]}>
                      {sc.enabled
                        ? new Date(sc.next_run_at).getTime() <= Date.now()
                          ? "next run due now"
                          : `next run in ${nextIn(sc.next_run_at)}`
                        : "paused"}
                      {sc.last_run_at ? ` · last ${timeAgo(sc.last_run_at)} ago` : ""}
                    </Text>
                  </View>
                  <View style={styles.rowActions}>
                    <Switch
                      value={sc.enabled}
                      onValueChange={(v) => {
                        toggleSchedule(sc.id, v).catch((e) =>
                          setError(e instanceof Error ? e.message : "Update failed."),
                        );
                      }}
                    />
                    <Button size="sm" variant="danger" onPress={() => confirmDelete(sc)}>
                      Delete
                    </Button>
                  </View>
                </View>
              </View>
            ))}
          </Card>
        )}
      </ScrollView>

      <TabBar active="schedules" />
    </View>
  );
}

/* Compact time-until, reusing timeAgo's units for a future timestamp. */
function nextIn(iso: string): string {
  const secs = Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000));
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  content: { paddingTop: 20, paddingHorizontal: 20, paddingBottom: 24 },
  headRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  notice: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
    marginBottom: 16,
  },
  row: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  rowActions: {
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: 10,
  },
});
