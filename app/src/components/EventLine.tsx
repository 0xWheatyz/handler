import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { radius, text } from "../theme/tokens";
import { useTheme } from "../theme/useTheme";
import { Badge } from "./Badge";
import { Mono } from "./primitives";
import type { AgentEvent } from "../api/client";

/**
 * One stream-json event of a headless run, rendered by type: assistant text as
 * prose, tool calls as badges, the result as a cost/turns footer, worker notices
 * as danger callouts, raw lines verbatim. RN port of the web dashboard's
 * EventLine (frontend RunsSection).
 */
export function EventLine({ event }: { event: AgentEvent }) {
  const { colors } = useTheme();
  const p = (event.payload ?? {}) as Record<string, any>;

  if (event.type === "system") {
    return (
      <Mono style={[styles.xs, { color: colors.textMuted }]}>
        ▸ session {p.subtype ?? "event"}
        {p.session_id ? ` · ${String(p.session_id).slice(0, 8)}` : ""}
        {Array.isArray(p.tools) ? ` · ${p.tools.length} tools` : ""}
      </Mono>
    );
  }

  if (event.type === "assistant") {
    const content = p.message?.content;
    const blocks: any[] = Array.isArray(content) ? content : [];
    const prose = blocks
      .filter((b) => b?.type === "text" && b.text)
      .map((b) => b.text)
      .join("\n");
    const tools = blocks.filter((b) => b?.type === "tool_use");
    return (
      <View style={{ gap: 6 }}>
        {prose ? (
          <Text style={[text.bodySm, { color: colors.textBody }]}>{prose}</Text>
        ) : null}
        {tools.length > 0 ? (
          <View style={styles.toolRow}>
            {tools.map((t, i) => (
              <Badge key={i} tone="neutral">
                {`${t.name}${t.input ? `: ${oneLine(t.input)}` : ""}`}
              </Badge>
            ))}
          </View>
        ) : null}
      </View>
    );
  }

  if (event.type === "result") {
    const err = Boolean(p.is_error);
    const meta = [
      p.num_turns != null ? `${p.num_turns} turns` : "",
      p.total_cost_usd != null ? `$${Number(p.total_cost_usd).toFixed(4)}` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    return (
      <View style={{ gap: 4 }}>
        <View style={styles.toolRow}>
          <Badge tone={err ? "danger" : "positive"}>
            {err ? "run errored" : "run finished"}
          </Badge>
          {meta ? (
            <Mono style={[styles.xs, { color: colors.textMuted }]}>{meta}</Mono>
          ) : null}
        </View>
        {typeof p.result === "string" && p.result ? (
          <Text style={[text.caption, { color: colors.textMuted }]}>{p.result}</Text>
        ) : null}
      </View>
    );
  }

  if (event.type === "worker") {
    return (
      <View
        style={[
          styles.notice,
          { backgroundColor: colors.dangerTint, borderColor: colors.danger },
        ]}
      >
        <Text style={[text.bodySm, { color: colors.danger }]}>
          {p.notice ?? "runner notice"}
        </Text>
        {p.stderr_tail ? (
          <Mono style={[styles.xs, { color: colors.danger, marginTop: 4 }]}>
            {p.stderr_tail}
          </Mono>
        ) : null}
      </View>
    );
  }

  if (event.type === "raw") {
    return (
      <Mono style={[styles.xs, { color: colors.textMuted }]}>
        {typeof p.line === "string" ? p.line.trimEnd() : JSON.stringify(p)}
      </Mono>
    );
  }

  // user (tool results) and anything future: a quiet one-liner, nothing lost, no noise.
  return (
    <Mono style={[styles.xs, { color: colors.textMuted }]}>▸ {event.type}</Mono>
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
  return s.length > 60 ? `${s.slice(0, 57)}…` : s;
}

const styles = StyleSheet.create({
  xs: { fontSize: 12, lineHeight: 18 },
  toolRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    alignItems: "center",
  },
  notice: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 10,
  },
});
