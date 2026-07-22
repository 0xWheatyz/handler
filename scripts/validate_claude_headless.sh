#!/usr/bin/env bash
# Phase-1 validation of the real `claude` binary's headless behavior (plan §0).
# Run MANUALLY inside the control container (needs real claude + credentials); findings
# go in the phase-1 PR description. Never wired into CI — this probes the real binary.
#
#   CLAUDE_BIN=claude ./scripts/validate_claude_headless.sh /tmp/headless-validation
#
# Each check prints PASS/FAIL/INFO; the script keeps going so one failure doesn't hide
# the rest. Items map to the plan's "must validate" list:
#   1. --verbose requirement with -p --output-format stream-json
#   2. exact stream-json event shapes for this CLI version
#   3. --resume from a transcript materialized onto a clean $HOME  (THE LINCHPIN)
#   4. PreToolUse deny behavior under -p
#   5. Stop-hook decision:block behavior under -p
#   6. -p exit-code semantics + credential env var name

set -uo pipefail

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
WORK="${1:-/tmp/headless-validation}"
SID="$(python3 -c 'import uuid; print(uuid.uuid4())')"

mkdir -p "$WORK/repo" "$WORK/home-a" "$WORK/home-b"
cd "$WORK/repo"

note() { printf '\n=== %s ===\n' "$*"; }
result() { printf -- '--> %s\n' "$*"; }

note "0. version"
"$CLAUDE_BIN" --version

note "1. does -p --output-format stream-json work WITHOUT --verbose?"
if HOME="$WORK/home-a" "$CLAUDE_BIN" -p --output-format stream-json \
    --session-id "$SID" -- 'Reply with the single word: ping' >"$WORK/no-verbose.out" 2>&1; then
  result "PASS without --verbose (flag optional — keep passing it anyway)"
else
  result "FAIL without --verbose (required, as the runner assumes): $(tail -1 "$WORK/no-verbose.out")"
fi

note "2. event shapes (fresh run, --verbose)"
SID2="$(python3 -c 'import uuid; print(uuid.uuid4())')"
HOME="$WORK/home-a" "$CLAUDE_BIN" -p --verbose --output-format stream-json \
  --session-id "$SID2" -- 'Reply with the single word: pong' \
  | tee "$WORK/stream.jsonl" \
  | python3 -c '
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        e = json.loads(line)
        keys = ",".join(sorted(e.keys()))
        print(f"  type={e.get(\"type\")}/{e.get(\"subtype\")} keys=[{keys}]")
    except Exception:
        print(f"  UNPARSEABLE: {line[:100]}")
'
result "exit code: $? — full stream saved to $WORK/stream.jsonl"

note "3. cross-worker resume: materialize transcript onto a clean HOME (LINCHPIN)"
MUNGED="$(python3 -c "import sys; print(sys.argv[1].replace('/', '-').replace('.', '-'))" "$WORK/repo")"
SRC="$WORK/home-a/.claude/projects/$MUNGED"
DST="$WORK/home-b/.claude/projects/$MUNGED"
mkdir -p "$DST"
if cp -r "$SRC/$SID2.jsonl" "$DST/" 2>/dev/null; then
  [ -d "$SRC/$SID2" ] && cp -r "$SRC/$SID2" "$DST/"
  if HOME="$WORK/home-b" "$CLAUDE_BIN" -p --verbose --output-format stream-json \
      --resume "$SID2" -- 'What word did you reply with before? Answer with just that word.' \
      >"$WORK/resume.jsonl" 2>"$WORK/resume.err"; then
    if grep -q 'pong' "$WORK/resume.jsonl"; then
      result "PASS: resume on clean HOME retained context (found 'pong')"
    else
      result "PARTIAL: resume ran but context unclear — inspect $WORK/resume.jsonl"
    fi
  else
    result "FAIL: resume on clean HOME errored — $(tail -1 "$WORK/resume.err") (fallback re-injection will be load-bearing)"
  fi
else
  result "FAIL: no transcript found at $SRC — munge algorithm wrong for this version?"
fi

note "4. PreToolUse deny under -p"
mkdir -p .claude
cat > .claude/settings.json <<'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {"type": "command",
           "command": "echo '{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"validation: always deny\"}}'"}
        ]
      }
    ]
  },
  "permissions": {"defaultMode": "acceptEdits", "allow": ["Bash(echo *)"]}
}
EOF
HOME="$WORK/home-a" "$CLAUDE_BIN" -p --verbose --output-format stream-json \
  --settings .claude/settings.json \
  -- 'Run the bash command `echo hello` and tell me its output.' \
  >"$WORK/deny.jsonl" 2>&1
result "exit=$? — grep the stream for the deny reason:"
grep -o 'validation: always deny' "$WORK/deny.jsonl" | head -1 \
  && result "PASS: deny reason surfaced in stream" \
  || result "INSPECT $WORK/deny.jsonl: deny reason not found"

note "5. Stop hook decision:block under -p"
cat > .claude/settings.json <<'EOF'
{
  "hooks": {
    "Stop": [
      {"hooks": [
        {"type": "command",
         "command": "if [ -f /tmp/.hv-stop-once ]; then echo '{}'; else touch /tmp/.hv-stop-once; echo '{\"decision\":\"block\",\"reason\":\"validation: say BLOCKED-ONCE then finish\"}'; fi"}
      ]}
    ]
  }
}
EOF
rm -f /tmp/.hv-stop-once
HOME="$WORK/home-a" "$CLAUDE_BIN" -p --verbose --output-format stream-json \
  --settings .claude/settings.json -- 'Reply with the word: initial' \
  >"$WORK/stopblock.jsonl" 2>&1
result "exit=$? — expect a second turn mentioning BLOCKED-ONCE:"
grep -o 'BLOCKED-ONCE' "$WORK/stopblock.jsonl" | head -1 \
  && result "PASS: Stop block re-prompted under -p" \
  || result "INSPECT $WORK/stopblock.jsonl: no evidence of re-prompt"
rm -f /tmp/.hv-stop-once

note "6. exit codes"
HOME="$WORK/home-a" "$CLAUDE_BIN" -p --verbose --output-format stream-json \
  --resume "$(python3 -c 'import uuid; print(uuid.uuid4())')" -- 'x' \
  >"$WORK/badresume.out" 2>&1
result "resume of nonexistent session exit=$? (runner treats nonzero-before-assistant as resume failure)"
result "INFO: check credential env name with: $CLAUDE_BIN setup-token --help (expect CLAUDE_CODE_OAUTH_TOKEN)"

note "done — artifacts in $WORK"
