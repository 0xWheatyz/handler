/**
 * handler-bridge — the pi extension that wires a pi agent into handler's hooks.
 *
 * Installed by `handler.control.pi_harness` into the per-agent PI_CODING_AGENT_DIR and
 * loaded with `-e`, so it runs on every pi-harness launch. It adapts pi's extension
 * events to the exact stdin/stdout contract of `python -m handler.hooks <event>` — all
 * gate logic (test gate, push gate, approval gate, question deferral, memory recall)
 * stays in the tested Python modules; this file only translates:
 *
 *  - before_agent_start  → hooks session_start (memory recall, injected once as context)
 *  - tool_call "bash"    → hooks pre_tool_use (git-push / merge-deploy gates; can block)
 *  - ask_operator tool   → hooks pre_tool_use as AskUserQuestion (defer + pause), then
 *                          terminates the run so the async answer/resume flow takes over
 *  - agent_settled       → hooks stop (the completion gate; a block is fed back as a
 *                          follow-up user message, continuing the run like claude's
 *                          Stop-hook re-invoke; stop_hook_active guards the loop)
 *  - session_shutdown    → hooks session_end
 *
 * It also registers the memory tools (memory_search/get/save/link) and dispatch_agent
 * that claude agents reach over MCP, by shelling to
 * `python -m handler.mcpserver --call <tool>` — pi has
 * no MCP by design, and a subprocess inheriting the agent env is the same trust model
 * the MCP server used anyway — plus web_search/web_fetch (`python -m handler.webtool`),
 * because pi ships no web tools and claude's live server-side at Anthropic.
 *
 * Identity and configuration arrive via the spawn environment, exactly like hooks:
 * HANDLER_AGENT_ID / HANDLER_PROJECT_ID / HANDLER_AGENT_NAME / DATABASE_URL, plus
 * HANDLER_PYTHON (the control layer's interpreter) and HANDLER_SESSION_ID (the run's
 * session UUID, which is also the session file's basename).
 */
import { spawnSync } from "node:child_process";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const PYTHON = process.env.HANDLER_PYTHON || "python3";
const SESSION_ID = process.env.HANDLER_SESSION_ID || "";
// The stop hook runs the project's own test suite; give it real time.
const STOP_HOOK_TIMEOUT_MS = 30 * 60 * 1000;
const HOOK_TIMEOUT_MS = 10 * 60 * 1000;

function runHook(event: string, payload: Record<string, unknown>, timeoutMs = HOOK_TIMEOUT_MS): any {
	const res = spawnSync(PYTHON, ["-m", "handler.hooks", event], {
		input: JSON.stringify({ session_id: SESSION_ID, cwd: process.cwd(), ...payload }),
		encoding: "utf8",
		timeout: timeoutMs,
	});
	if (res.error || res.status !== 0) {
		const detail = res.error ? String(res.error) : (res.stderr || "").slice(-2000);
		process.stderr.write(`handler-bridge: hook ${event} failed: ${detail}\n`);
		return null;
	}
	const line = (res.stdout || "").trim().split("\n").filter(Boolean).pop();
	if (!line) return {};
	try {
		return JSON.parse(line);
	} catch {
		return {};
	}
}

function callPython(moduleArgs: string[], toolName: string, args: Record<string, unknown>): string {
	const res = spawnSync(PYTHON, moduleArgs, {
		input: JSON.stringify(args ?? {}),
		encoding: "utf8",
		timeout: 60_000,
	});
	if (res.error || res.status !== 0) {
		const detail = res.error ? String(res.error) : (res.stderr || "").slice(-2000);
		throw new Error(`${toolName} failed: ${detail}`);
	}
	return (res.stdout || "").trim() || "{}";
}

// The bundled MCP server's one-shot seam: same tool implementations claude reaches
// over MCP (memory + dispatch), same identity-from-environment contract.
function callMcpTool(tool: string, args: Record<string, unknown>): string {
	return callPython(["-m", "handler.mcpserver", "--call", tool], tool, args);
}

function callWeb(tool: string, args: Record<string, unknown>): string {
	return callPython(["-m", "handler.webtool", tool], tool, args);
}

function permissionDeny(out: any): string | null {
	const spec = out?.hookSpecificOutput;
	if (spec?.permissionDecision === "deny") {
		return String(spec.permissionDecisionReason || "denied by handler");
	}
	return null;
}

export default function (pi: ExtensionAPI) {
	let contextInjected = false;
	let askDeferred = false;
	let stopRounds = 0;
	let lastAssistantText = "";

	// Tool parity with the claude harness: pi ships read/write/edit/bash active and
	// leaves grep/find/ls off by default. Enable everything registered — the built-ins
	// plus this bridge's own tools. (The --tools flag can't do this: it is a strict
	// allowlist that would drop extension tools.)
	pi.on("session_start", async () => {
		pi.setActiveTools(pi.getAllTools().map((t) => t.name));
	});

	// ---- memory recall at session start (claude's SessionStart hook) ----------------
	pi.on("before_agent_start", async () => {
		if (contextInjected) return;
		contextInjected = true;
		const out = runHook("session_start", {});
		const text = out?.hookSpecificOutput?.additionalContext;
		if (typeof text === "string" && text.trim()) {
			return {
				message: { customType: "handler-context", content: text, display: true },
			};
		}
	});

	// ---- PreToolUse gates ------------------------------------------------------------
	pi.on("tool_call", async (event) => {
		if (event.toolName === "bash") {
			const command = String((event.input as any)?.command ?? "");
			// Cheap pre-filter mirroring the hook's own matchers: only push/merge/deploy
			// commands pay for a hook subprocess; everything else runs untouched.
			if (!/\bgit\s+push\b|\bforge\s+(?:pr\s+)?merge\b|\bmise\s+run\s+deploy\b/.test(command)) return;
			const out = runHook(
				"pre_tool_use",
				{ tool_name: "Bash", tool_input: { command } },
				STOP_HOOK_TIMEOUT_MS, // the push gate runs tests + an image build
			);
			const reason = permissionDeny(out);
			if (reason) return { block: true, reason };
			return;
		}
		if (event.toolName === "ask_operator") {
			const question = String((event.input as any)?.question ?? "").trim();
			const out = runHook("pre_tool_use", {
				tool_name: "AskUserQuestion",
				tool_input: { questions: [{ question }] },
			});
			askDeferred = true;
			runHook("notification", { message: `question for the operator: ${question}`.slice(0, 500) });
			const reason =
				permissionDeny(out) ||
				"Question deferred to the operator; the run pauses here and resumes with the answer.";
			// terminate: the operator answers asynchronously (answer + resume); there is
			// nothing useful this process can do while it waits.
			return { block: true, reason, terminate: true };
		}
	});

	// ---- the completion gate (claude's Stop hook) -------------------------------------
	pi.on("message_end", async (event) => {
		const m: any = (event as any).message;
		if (m?.role === "assistant" && Array.isArray(m.content)) {
			const text = m.content
				.filter((b: any) => b?.type === "text" && b.text)
				.map((b: any) => b.text)
				.join("\n")
				.trim();
			if (text) lastAssistantText = text;
		}
	});

	pi.on("agent_settled", async () => {
		if (askDeferred) return; // paused_for_input is already the checkpoint of record
		const out = runHook(
			"stop",
			{
				stop_hook_active: stopRounds > 0,
				final_assistant_text: lastAssistantText || null,
			},
			STOP_HOOK_TIMEOUT_MS,
		);
		if (out?.decision === "block" && out.reason) {
			stopRounds += 1;
			pi.sendUserMessage(String(out.reason), { deliverAs: "followUp" });
		}
	});

	pi.on("session_shutdown", async () => {
		if (askDeferred) return;
		runHook("session_end", { reason: "session ended" });
	});

	// ---- the operator question tool ----------------------------------------------------
	pi.registerTool({
		name: "ask_operator",
		label: "Ask operator",
		description:
			"Ask the human operator a question you cannot answer yourself (a decision, a " +
			"credential, an ambiguity in the task). The run pauses; the operator's answer " +
			"arrives when the session is resumed. Ask only when genuinely blocked.",
		parameters: Type.Object({
			question: Type.String({ description: "The question for the operator" }),
		}),
		async execute() {
			// Normally unreachable: the tool_call handler defers the question and
			// terminates the run before execution.
			return {
				content: [{ type: "text", text: "Question recorded; the run will pause for the operator." }],
				details: {},
			};
		},
	});

	// ---- memory tools (the handler-memory MCP server's surface, sans MCP) --------------
	const memoryTools: Array<{ name: string; label: string; description: string; parameters: any }> = [
		{
			name: "memory_search",
			label: "Memory search",
			description:
				"Search the team memory store (notes left by earlier agent runs and the operator) " +
				"for your project plus global notes. Every whitespace-separated term must match " +
				"the title, body, or kind (case-insensitive). An empty query returns the most " +
				"recent notes. Use this BEFORE re-deriving how something works.",
			parameters: Type.Object({
				query: Type.Optional(Type.String({ description: "Search terms; empty = recent notes" })),
				limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 50 })),
			}),
		},
		{
			name: "memory_get",
			label: "Memory get",
			description: "Fetch one memory note in full, including its links to other notes.",
			parameters: Type.Object({
				note_id: Type.Integer({ description: "The note id" }),
			}),
		},
		{
			name: "memory_save",
			label: "Memory save",
			description:
				"Save durable knowledge for future agent runs: a fact, a decision and its " +
				"rationale, a gotcha, or a runbook. Write for a reader with no context from this " +
				"session. Pass note_id to update; pass global=true only for cross-project knowledge.",
			parameters: Type.Object({
				title: Type.String({ description: "Short, searchable headline" }),
				body: Type.String({ description: "The knowledge itself, markdown ok" }),
				kind: Type.Optional(Type.String({ description: "fact | decision | gotcha | runbook" })),
				tags: Type.Optional(Type.Array(Type.String())),
				note_id: Type.Optional(Type.Integer({ description: "Update this note instead" })),
				global: Type.Optional(Type.Boolean({ description: "Store unscoped (all projects)" })),
			}),
		},
		{
			name: "memory_link",
			label: "Memory link",
			description:
				"Connect two memory notes so the knowledge graph shows how they relate. " +
				"Idempotent: repeating an existing link is fine.",
			parameters: Type.Object({
				src_note_id: Type.Integer(),
				dst_note_id: Type.Integer(),
				relation: Type.Optional(Type.String({ description: "default: relates_to" })),
			}),
		},
	];
	for (const tool of memoryTools) {
		pi.registerTool({
			...tool,
			async execute(_toolCallId: string, params: Record<string, unknown>) {
				const text = callMcpTool(tool.name, params ?? {});
				return { content: [{ type: "text", text }], details: {} };
			},
		});
	}

	// ---- dispatch (same MCP seam): hand work to a new agent in this project ------------
	pi.registerTool({
		name: "dispatch_agent",
		label: "Dispatch agent",
		description:
			"Hand work to a NEW agent in this project, which starts as soon as a worker is " +
			"free. Use when your run produced something concrete for a different role to act " +
			"on. This is a handoff, not a fan-out: dispatch once per thing you found, and only " +
			"when there is real work — finding nothing is a complete run, so say so and end " +
			"your turn instead. The new agent has NO memory of this session, so 'task' must " +
			"stand on its own: what to do, which files or sources, and anything it would " +
			"otherwise have to rediscover.",
		parameters: Type.Object({
			name_prefix: Type.String({ description: "Short slug; a timestamp is appended" }),
			task: Type.String({ description: "The new agent's whole prompt — self-contained" }),
			reason: Type.String({ description: "Why this handoff is warranted (for the operator)" }),
			role: Type.Optional(
				Type.String({ description: "scout | planner | junior | senior | deploy" }),
			),
			model_id: Type.Optional(Type.Integer({ description: "Model backend for the new agent" })),
			worktree: Type.Optional(Type.String({ description: "Branch for a per-run worktree" })),
			subdir: Type.Optional(Type.String({ description: "Subdir under the project root" })),
		}),
		async execute(_toolCallId: string, params: Record<string, unknown>) {
			const text = callMcpTool("dispatch_agent", params ?? {});
			return { content: [{ type: "text", text }], details: {} };
		},
	});

	// ---- web tools (handler.webtool — pi ships none, claude's are Anthropic-server-side)
	const webTools: Array<{ name: string; label: string; description: string; parameters: any }> = [
		{
			name: "web_search",
			label: "Web search",
			description:
				"Search the web. Returns titles, URLs, and snippets; follow up with web_fetch " +
				"to read a promising result in full. Provider is operator-configured " +
				"(SearXNG / Brave / DuckDuckGo fallback).",
			parameters: Type.Object({
				query: Type.String({ description: "The search query" }),
				limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 10 })),
			}),
		},
		{
			name: "web_fetch",
			label: "Web fetch",
			description:
				"Fetch a URL and return its readable text (HTML is stripped; other content " +
				"types come back as-is, truncated). Use for docs, changelogs, issues, articles.",
			parameters: Type.Object({
				url: Type.String({ description: "The http(s) URL to fetch" }),
				max_chars: Type.Optional(
					Type.Integer({ minimum: 1000, maximum: 100000, description: "Text cap (default 20000)" }),
				),
			}),
		},
	];
	for (const tool of webTools) {
		pi.registerTool({
			...tool,
			async execute(_toolCallId: string, params: Record<string, unknown>) {
				const text = callWeb(tool.name, params ?? {});
				return { content: [{ type: "text", text }], details: {} };
			},
		});
	}
}
