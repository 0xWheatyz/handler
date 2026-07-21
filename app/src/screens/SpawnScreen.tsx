import React, { useEffect, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { radius, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { Select } from "../components/Select";
import { TextField } from "../components/TextField";
import { useAppState } from "../state/AppState";

export function SpawnScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { go, projects, spawn } = useAppState();

  const projectIds = projects.map((p) => p.id);
  const [project, setProject] = useState("");
  const [task, setTask] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Default to the first project once they load (or if the current pick vanished).
  useEffect(() => {
    if (projectIds.length > 0 && !projectIds.includes(project)) {
      setProject(projectIds[0]);
    }
  }, [projectIds, project]);

  async function submit() {
    if (!project) {
      setError("Pick a project first.");
      return;
    }
    if (!task.trim()) {
      setError("Describe the task.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await spawn(project, task.trim());
      go("fleet");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t spawn the agent.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[styles.page, { backgroundColor: colors.surfacePage }]}>
      <View style={{ height: insets.top }} />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={[styles.content, { paddingBottom: insets.bottom + 20 }]}>
          <PageHeader
            leading="close"
            onLeadingPress={() => go("fleet")}
            title="New agent"
          />

          <View style={{ gap: 16 }}>
            {projectIds.length > 0 ? (
              <Select
                label="Project"
                options={projectIds}
                value={project || projectIds[0]}
                onChange={setProject}
              />
            ) : (
              <View>
                <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                  Project
                </Text>
                <Text style={[text.bodySm, { color: colors.textMuted }]}>
                  No projects registered yet.
                </Text>
              </View>
            )}

            <View>
              <Text style={[text.label, { color: colors.textHeading, marginBottom: 6 }]}>
                Task
              </Text>
              <TextField
                value={task}
                onChangeText={setTask}
                placeholder="What should this agent do?"
                multiline
                height={120}
              />
              <Text style={[text.caption, { color: colors.textMuted, marginTop: 6 }]}>
                Runs isolated on a fresh branch.
              </Text>
            </View>

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
          </View>

          <View style={{ marginTop: "auto" }}>
            <Button
              size="lg"
              style={{ width: "100%" }}
              onPress={busy ? undefined : submit}
            >
              {busy ? "Spawning…" : "Spawn agent"}
            </Button>
          </View>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  flex: { flex: 1 },
  content: { flex: 1, paddingTop: 8, paddingHorizontal: 20 },
  notice: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
  },
});
