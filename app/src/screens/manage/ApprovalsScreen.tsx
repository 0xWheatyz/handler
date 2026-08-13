import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { text } from "../../theme/tokens";
import { useTheme } from "../../theme/useTheme";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { ErrorNotice, Field, ManageShell } from "../../components/ManageShell";
import { Select } from "../../components/Select";
import { TextField } from "../../components/TextField";
import { Card, Divider, Mono, SectionLabel } from "../../components/primitives";
import { useAppState } from "../../state/AppState";
import { useResource } from "../../state/useResource";
import { statusLabel, statusTone, timeAgo } from "../../api/format";
import type { Approval, Command } from "../../api/client";

/**
 * Approvals — record a per-branch verdict (the review gate), the mobile counterpart
 * of the web dashboard's Approvals section. A verdict is enqueued as a control
 * command so the worker can resolve the reviewed HEAD and pin the approval.
 */

/* "agent #N" for agent-made verdicts, else the recorded actor (operator:web etc). */
function verdictBy(ap: Approval): string | null {
  if (ap.approved_by_agent_id != null) return `agent #${ap.approved_by_agent_id}`;
  return ap.actor || null;
}

export function ApprovalsScreen() {
  const { colors } = useTheme();
  const { client, projects } = useAppState();

  const projectIds = projects.map((p) => p.id);
  const [project, setProject] = useState("");
  const [branch, setBranch] = useState("");
  const [sha, setSha] = useState("");
  const [pr, setPr] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (projectIds.length > 0 && !projectIds.includes(project)) {
      setProject(projectIds[0]);
    }
  }, [projectIds, project]);

  const {
    data: approvals,
    error: loadError,
    loading,
    reload,
  } = useResource<Approval[]>(
    project ? `/projects/${encodeURIComponent(project)}/approvals` : null,
  );

  async function submit(status: "approved" | "rejected") {
    if (!client || !project) return;
    if (!branch.trim()) {
      setError("Branch is required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const cmd = await client.api<Command>(
        `/projects/${encodeURIComponent(project)}/approvals`,
        {
          body: {
            branch: branch.trim(),
            status,
            ...(sha.trim() ? { sha: sha.trim() } : {}),
            ...(pr.trim() ? { pr: pr.trim() } : {}),
            ...(note.trim() ? { note: note.trim() } : {}),
          },
        },
      );
      const tracked = await client.trackCommand(cmd.id);
      if (tracked?.status === "failed") {
        setError(tracked.error || "The verdict command failed.");
      } else {
        setBranch("");
        setSha("");
        setPr("");
        setNote("");
      }
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t record the verdict.");
    } finally {
      setBusy(false);
    }
  }

  const rows = approvals ?? [];

  return (
    <ManageShell
      title="Approvals"
      subtitle="A merge is denied unless a standing approval exists — made by a second party, pinned to the reviewed commit."
    >
      {projectIds.length === 0 ? (
        <Text style={[text.bodySm, { color: colors.textMuted }]}>
          Register a repository first.
        </Text>
      ) : (
        <>
          <View style={{ marginBottom: 16 }}>
            <Select
              label="Repository"
              options={projectIds}
              value={project || projectIds[0]}
              onChange={setProject}
            />
          </View>

          <Card style={{ padding: 16, marginBottom: 16, gap: 14 }}>
            <SectionLabel>Record a verdict</SectionLabel>
            <Field label="Branch">
              <TextField
                value={branch}
                onChangeText={setBranch}
                placeholder="feat/auth"
                autoCapitalize="none"
                autoCorrect={false}
              />
            </Field>
            <Field
              label="Sha"
              hint="Optional — defaults to the branch head resolved by the worker."
            >
              <TextField
                value={sha}
                onChangeText={setSha}
                placeholder="pins the approval"
                autoCapitalize="none"
                autoCorrect={false}
              />
            </Field>
            <Field label="PR ref">
              <TextField
                value={pr}
                onChangeText={setPr}
                placeholder="optional"
                autoCapitalize="none"
                autoCorrect={false}
              />
            </Field>
            <Field label="Note">
              <TextField value={note} onChangeText={setNote} placeholder="optional" />
            </Field>
            <View style={styles.verdictRow}>
              <Button
                style={{ flex: 1 }}
                onPress={busy ? undefined : () => submit("approved")}
              >
                {busy ? "Enqueuing…" : "Approve"}
              </Button>
              <Button
                variant="danger"
                style={{ flex: 1 }}
                onPress={busy ? undefined : () => submit("rejected")}
              >
                {busy ? "Enqueuing…" : "Reject"}
              </Button>
            </View>
          </Card>

          <ErrorNotice message={error ?? loadError} />

          <SectionLabel style={{ marginBottom: 8 }}>
            {`${rows.length} verdict${rows.length === 1 ? "" : "s"}`}
          </SectionLabel>

          {rows.length === 0 ? (
            <Text style={[text.bodySm, { color: colors.textMuted }]}>
              {loading ? "Loading…" : "No approvals recorded."}
            </Text>
          ) : (
            <Card>
              {rows.map((ap, i) => (
                <View key={ap.id}>
                  {i > 0 && <Divider />}
                  <View style={styles.row}>
                    <View style={styles.titleRow}>
                      <Mono style={{ fontSize: 14, color: colors.textHeading }}>
                        {ap.branch}
                      </Mono>
                      <Badge tone={statusTone(ap.status)}>
                        {statusLabel(ap.status)}
                      </Badge>
                    </View>
                    <Text style={[text.caption, { color: colors.textMuted }]}>
                      {[
                        ap.approved_sha ? ap.approved_sha.slice(0, 8) : null,
                        ap.pr_ref,
                        verdictBy(ap),
                        `${timeAgo(ap.created_at)} ago`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </Text>
                    {ap.note ? (
                      <Text
                        numberOfLines={2}
                        style={[text.caption, { color: colors.textMuted }]}
                      >
                        {ap.note}
                      </Text>
                    ) : null}
                  </View>
                </View>
              ))}
            </Card>
          )}
        </>
      )}
    </ManageShell>
  );
}

const styles = StyleSheet.create({
  verdictRow: {
    flexDirection: "row",
    gap: 10,
  },
  row: {
    gap: 4,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
});
