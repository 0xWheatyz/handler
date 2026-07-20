import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { Select } from "../components/Select";
import { TextField } from "../components/TextField";
import { ToggleRow } from "../components/ToggleRow";
import { Card, Divider } from "../components/primitives";
import { useAppState } from "../state/AppState";
import { projectOptions } from "../data/mock";

export function SpawnScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { go, spawnGo, swEdits, setSwEdits, swTests, setSwTests } = useAppState();
  const [project, setProject] = useState("handler");
  const [task, setTask] = useState("");

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
            <Select
              label="Project"
              options={projectOptions}
              value={project}
              onChange={setProject}
            />

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

            <Card>
              <ToggleRow
                title="Auto-approve edits"
                subtitle="Skip file-edit confirmations"
                value={swEdits}
                onValueChange={setSwEdits}
              />
              <Divider />
              <ToggleRow
                title="Run tests on done"
                subtitle="Checkmark fails if tests fail"
                value={swTests}
                onValueChange={setSwTests}
              />
            </Card>
          </View>

          <View style={{ marginTop: "auto" }}>
            <Button size="lg" style={{ width: "100%" }} onPress={spawnGo}>
              Spawn agent
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
});
