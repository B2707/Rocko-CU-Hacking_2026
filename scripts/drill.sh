#!/usr/bin/env bash
# drill.sh — scripted tripwire fires (D4 deterministic drill, audit C2).
# Dispatches every tripwire through the REAL Discord alert path with a
# [DRILL] prefix, then verifies all workflow runs completed. The binary
# checkpoint is human: #ops must show exactly 3 [DRILL][P0] lines
# (red-main, panic, demo-freeze) and #feed exactly 5 [DRILL][P1] lines
# (stuck-pr, stale-claim, collision, deadlock, budget). Anything else =
# wiring broken; fix before the D5 team drill.
#
# Usage: scripts/drill.sh <owner/repo>
# Run once, freshly — verification reads the newest 8 dispatch runs.
set -euo pipefail

REPO="${1:?usage: drill.sh <owner/repo>}"
WIRES=(red-main stuck-pr stale-claim panic collision deadlock budget demo-freeze)
TIMEOUT_S=300

echo "==> dispatching ${#WIRES[@]} drill fires on $REPO"
for wire in "${WIRES[@]}"; do
  gh workflow run tripwires.yml --repo "$REPO" -f simulate="$wire"
  echo "    fired: $wire"
done

echo "==> waiting for runs to register and complete (max ${TIMEOUT_S}s)"
sleep 15
deadline=$((SECONDS + TIMEOUT_S))
while :; do
  completed=$(gh run list --repo "$REPO" --workflow tripwires.yml \
    --event workflow_dispatch --limit "${#WIRES[@]}" \
    --json status --jq '[.[] | select(.status == "completed")] | length')
  echo "    completed: $completed/${#WIRES[@]}"
  [ "$completed" -ge "${#WIRES[@]}" ] && break
  if [ "$SECONDS" -gt "$deadline" ]; then
    echo "FAIL: drill runs did not complete within ${TIMEOUT_S}s" >&2
    exit 1
  fi
  sleep 10
done

successes=$(gh run list --repo "$REPO" --workflow tripwires.yml \
  --event workflow_dispatch --limit "${#WIRES[@]}" \
  --json conclusion --jq '[.[] | select(.conclusion == "success")] | length')

if [ "$successes" -ne "${#WIRES[@]}" ]; then
  echo "FAIL: $successes/${#WIRES[@]} drill runs succeeded — inspect: gh run list --workflow tripwires.yml --repo $REPO" >&2
  exit 1
fi

echo "==> PASS: ${#WIRES[@]}/${#WIRES[@]} drill runs green"
echo
echo "BINARY CHECKPOINT (a human answers yes/no):"
echo "  1. #ops shows exactly 3 [DRILL][P0] lines (red-main, panic, demo-freeze)?"
echo "  2. #feed shows exactly 5 [DRILL][P1] lines (stuck-pr, stale-claim, collision, deadlock, budget)?"
echo "If either answer is no: webhook secrets are missing/mis-wired — see docs/RUNBOOKS.md."
