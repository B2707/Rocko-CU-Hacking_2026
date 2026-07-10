#!/usr/bin/env bash
# Proves the PreToolUse gates actually DENY. Hooks fail open, so a silently
# broken gate would pass unnoticed (canon: workflow-enforcement-and-hooks.md —
# every blocking gate must be tested to prove it blocks). Run by CI (hooks-test
# job) and manually. Exits non-zero on the first gate that fails to deny.
set -euo pipefail
cd "$(dirname "$0")/.."

HOOKS="scripts/hooks"
pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1" >&2; exit 1; }

# Feed a crafted PreToolUse payload on stdin; assert stdout carries a deny.
assert_deny() {
  local name="$1" hook="$2" payload="$3" out
  out="$(printf '%s' "$payload" | node "$hook" 2>/dev/null || true)"
  if printf '%s' "$out" | grep -q '"permissionDecision":"deny"'; then
    pass "$name denies"
  else
    fail "$name did NOT deny (output: ${out:-<empty>})"
  fi
}

# Assert the hook does NOT deny (allows the action through).
assert_allow() {
  local name="$1" hook="$2" payload="$3" out
  out="$(printf '%s' "$payload" | node "$hook" 2>/dev/null || true)"
  if printf '%s' "$out" | grep -q '"permissionDecision":"deny"'; then
    fail "$name denied when it should allow (output: $out)"
  else
    pass "$name allows"
  fi
}

echo "==> bash-guard: push to main is denied"
assert_deny "bash-guard push-main" "$HOOKS/bash-guard.js" \
  '{"cwd":"'"$PWD"'","tool_input":{"command":"git push origin main"}}'

echo "==> bash-guard: direct gh issue create is denied"
assert_deny "bash-guard gh-issue-create" "$HOOKS/bash-guard.js" \
  '{"cwd":"'"$PWD"'","tool_input":{"command":"gh issue create --title x"}}'

echo "==> bash-guard: an ordinary command is allowed"
assert_allow "bash-guard ls" "$HOOKS/bash-guard.js" \
  '{"cwd":"'"$PWD"'","tool_input":{"command":"ls -la"}}'

echo "==> fact-gate: first edit of a code file is denied (fresh session)"
SID="test-$$-${RANDOM}"
FACT_PAYLOAD='{"session_id":"'"$SID"'","cwd":"'"$PWD"'","tool_input":{"file_path":"'"$PWD"'/src/probe.ts"}}'
assert_deny "fact-gate first-edit" "$HOOKS/fact-gate.js" "$FACT_PAYLOAD"

echo "==> fact-gate: the second identical edit is allowed (deny-once)"
assert_allow "fact-gate second-edit" "$HOOKS/fact-gate.js" "$FACT_PAYLOAD"

echo "==> fact-gate: a data/context file is never fact-gated"
assert_allow "fact-gate skip-context" "$HOOKS/fact-gate.js" \
  '{"session_id":"'"$SID"'-c","cwd":"'"$PWD"'","tool_input":{"file_path":"'"$PWD"'/data/context/handoffs/probe.md"}}'

echo "==> fact-gate: one-writer surface (gotchas.md) denied for a non-manager seat"
TEAM_SEAT=amr assert_deny "fact-gate one-writer seat" "$HOOKS/fact-gate.js" \
  '{"session_id":"'"$SID"'-w1","cwd":"'"$PWD"'","tool_input":{"file_path":"'"$PWD"'/data/context/gotchas.md"}}'

echo "==> fact-gate: one-writer surface allowed for the manager seat"
TEAM_SEAT=bader assert_allow "fact-gate one-writer manager" "$HOOKS/fact-gate.js" \
  '{"session_id":"'"$SID"'-w2","cwd":"'"$PWD"'","tool_input":{"file_path":"'"$PWD"'/data/context/gotchas.md"}}'

echo "ALL HOOK GATES PROVEN"
