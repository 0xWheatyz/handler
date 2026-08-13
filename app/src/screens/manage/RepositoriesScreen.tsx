import React, { useEffect, useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Select } from "../../components/Select";
import { Switch } from "../../components/Switch";
import { TextField } from "../../components/TextField";
import { Card, Divider, Mono, SectionLabel } from "../../components/primitives";
import { timeAgo } from "../../api/format";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import type { Command, Host, Project } from "../../api/client";

/**
 * Repositories — register + sync the repos Handler manages, the mobile
 * counterpart of the web dashboard's Repositories section. The preferred path
 * is git-server mode: pick a configured forge host and type owner/name; the
 * server derives the remote, clones under PROJECTS_ROOT, and keeps it fresh.
 * Manual mode registers an existing checkout by absolute path.
 */

const REPO_RE = /^[\w.-]+\/[\w.-]+$/;

type Mode = "server" | "manual";

const enc = encodeURIComponent;

export function RepositoriesScreen() {
  const { colors } = useTheme();
  const { client, refresh } = useAppState();
  const projectsRes = useResource<Project[]>("/projects");
  const hostsRes = useResource<Host[]>("/hosts");
  const projects = projectsRes.data ?? [];
  const hosts = hostsRes.data ?? [];
  const hostnames = hosts.map((h) => h.hostname);

  const [showForm, setShowForm] = useState(false);
  const [mode, setMode] = useState<Mode>("server");
  const [gitServer, setGitServer] = useState("");
  const [repo, setRepo] = useState("");
  const [projectId, setProjectId] = useState("");
  const [initMise, setInitMise] = useState(false);
  const [rootDir, setRootDir] = useState("");
  const [gitRemote, setGitRemote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Project id of the last enqueued sync — shows a transient "sync queued" note.
  const [syncedId, setSyncedId] = useState<string | null>(null);

  // Default to the first git server once hosts load (or if the pick vanished).
  useEffect(() => {
    if (hostnames.length > 0 && !hostnames.includes(gitServer)) {
      setGitServer(hostnames[0]);
    }
  }, [hostnames, gitServer]);

  function resetForm() {
    setRepo("");
    setProjectId("");
    setInitMise(false);
    setRootDir("");
    setGitRemote("");
    setShowForm(false);
  }

  async function register() {
    if (!client) return;
    if (mode === "server") {
      if (!gitServer) {
        setError("Pick a git server first (add one under Git servers).");
        return;
      }
      if (!REPO_RE.test(repo.trim())) {
        setError("Repository must be owner/name.");
        return;
      }
    } else if (!projectId.trim() || !rootDir.trim()) {
      setError("Project id and root dir are both required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const body =
        mode === "server"
          ? {
              git_server: gitServer,
              repo: repo.trim(),
              id: projectId.trim() || undefined,
              init_mise: initMise,
            }
          : {
              id: projectId.trim(),
              root_dir: rootDir.trim(),
              git_remote: gitRemote.trim() || undefined,
            };
      await client.api<Project>("/projects", { body });
      resetForm();
      await refresh();
      projectsRes.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t register the repository.");
    } finally {
      setBusy(false);
    }
  }

  async function sync(p: Project) {
    if (!client) return;
    setError(null);
    try {
      await client.api<Command>(`/projects/${enc(p.id)}/sync`, { method: "POST" });
      setSyncedId(p.id);
      setTimeout(() => setSyncedId((cur) => (cur === p.id ? null : cur)), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed.");
    }
  }

  function confirmDelete(p: Project) {
    Alert.alert(
      "Delete repository?",
      `Unregister ${p.id} from Handler. The checkout on disk is not touched.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            client
              ?.api(`/projects/${enc(p.id)}`, { method: "DELETE" })
              .then(() => {
                projectsRes.reload();
                return refresh();
              })
              .catch((e) =>
                setError(e instanceof Error ? e.message : "Delete failed."),
              );
          },
        },
      ],
    );
  }

  return (
    <ManageShell
      title="Repositories"
      subtitle="Repos Handler manages. Each carries its own agents, history, and credentials."
    >
      <View style={styles.headRow}>
        <SectionLabel>
          {`${projects.length} repositor${projects.length === 1 ? "y" : "ies"}`}
        </SectionLabel>
        <Button
          size="sm"
          variant={showForm ? "secondary" : "primary"}
          onPress={() => setShowForm((v) => !v)}
        >
          {showForm ? "Cancel" : "New"}
        </Button>
      </View>

      {showForm ? (
        <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
          <SegmentedControl<Mode>
            segments={[
              { value: "server", label: "Git server" },
              { value: "manual", label: "Manual" },
            ]}
            value={mode}
            onChange={setMode}
          />

          {mode === "server" ? (
            <>
              {hostnames.length > 0 ? (
                <Select
                  label="Git server"
                  options={hosts.map((h) => ({
                    value: h.hostname,
                    label: `${h.hostname} (${h.forge_type})`,
                  }))}
                  value={gitServer || hostnames[0]}
                  onChange={setGitServer}
                />
              ) : (
                <Field
                  label="Git server"
                  hint="No git servers configured — add one under Git servers first."
                >
                  <Text style={[text.bodySm, { color: colors.textMuted }]}>
                    None registered yet.
                  </Text>
                </Field>
              )}
              <Field
                label="Repository"
                hint="The server derives the remote, clones it, and keeps it fresh before every run."
              >
                <TextField
                  value={repo}
                  onChangeText={setRepo}
                  placeholder="owner/name"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </Field>
              <Field label="Project id" hint="Optional — defaults to a slug of the repo name.">
                <TextField
                  value={projectId}
                  onChangeText={setProjectId}
                  placeholder="coolproj"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </Field>
              <View style={styles.switchRow}>
                <View style={{ flex: 1 }}>
                  <Text style={[text.label, { color: colors.textHeading }]}>
                    Initialize mise
                  </Text>
                  <Text style={[text.caption, { color: colors.textMuted, marginTop: 2 }]}>
                    Queues a bootstrap agent that authors .mise.toml with a test
                    task and pushes it.
                  </Text>
                </View>
                <Switch value={initMise} onValueChange={setInitMise} />
              </View>
            </>
          ) : (
            <>
              <Field label="Project id">
                <TextField
                  value={projectId}
                  onChangeText={setProjectId}
                  placeholder="leeworks-api"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </Field>
              <Field label="Root dir" hint="Absolute path on the control container.">
                <TextField
                  value={rootDir}
                  onChangeText={setRootDir}
                  placeholder="/var/lib/handler/projects/leeworks"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </Field>
              <Field label="Git remote" hint="Optional — needed for Sync and pushes.">
                <TextField
                  value={gitRemote}
                  onChangeText={setGitRemote}
                  placeholder="git@github.com:user/repo.git"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </Field>
            </>
          )}

          <Button size="lg" style={{ width: "100%" }} onPress={busy ? undefined : register}>
            {busy ? "Registering…" : mode === "server" ? "Add & pull" : "Register"}
          </Button>
        </Card>
      ) : null}

      <ErrorNotice message={error ?? projectsRes.error} />

      {projectsRes.loading && projects.length === 0 ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>Loading…</Text>
      ) : projects.length === 0 ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          No repositories registered.
        </Text>
      ) : (
        <Card>
          {projects.map((p, i) => (
            <View key={p.id}>
              {i > 0 && <Divider />}
              <View style={styles.row}>
                <View style={{ flex: 1, gap: 4 }}>
                  <View style={styles.titleRow}>
                    <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                      {p.id}
                    </Mono>
                    {p.owner_user_id != null ? (
                      <Badge tone="neutral">private</Badge>
                    ) : null}
                  </View>
                  <Mono
                    numberOfLines={1}
                    style={{ fontSize: 12, color: colors.textMuted }}
                  >
                    {p.git_remote || p.root_dir}
                  </Mono>
                  <Text style={[text.caption, { color: colors.textMuted }]}>
                    added {timeAgo(p.created_at)} ago
                  </Text>
                  {syncedId === p.id ? (
                    <Text style={[text.caption, { color: colors.positive }]}>
                      sync queued
                    </Text>
                  ) : null}
                </View>
                <View style={styles.rowActions}>
                  {p.git_remote ? (
                    <Button size="sm" variant="secondary" onPress={() => sync(p)}>
                      Sync
                    </Button>
                  ) : null}
                  <Button size="sm" variant="danger" onPress={() => confirmDelete(p)}>
                    Delete
                  </Button>
                </View>
              </View>
            </View>
          ))}
        </Card>
      )}
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  headRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
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
    justifyContent: "flex-start",
    gap: 10,
  },
});
