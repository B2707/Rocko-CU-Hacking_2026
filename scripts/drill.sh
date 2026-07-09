#!/usr/bin/env bash
# drill.sh — scripted tripwire drill (D4 deterministic drill, audit C2).
# Fires ALL eight tripwire samples through the REAL Discord alert path with a
# [DRILL] prefix in a SINGLE workflow run (simulate=all, handled in
# tripwires.js). One run = one runner cold-start and one status poll, so the
# drill is ~8x faster than the old wire-by-wire loop and far less exposed to a
# transient GitHub API blip killing it mid-way. No serial firing needed: a
# single run never contends with itself on the `tripwires` concurrency group.
# The binary checkpoint is human: #ops must show exactly 3 [DRILL][P0] lines
# (red-main, panic, demo-freeze) and #feed exactly 5 [DRILL][P1] lines
# (stuck-pr, stale-claim, collision, deadlock, budget).
# Anything else = wiring broken; fix before the D5 team drill.
#
# Usage: scripts/drill.sh <owner/repo>
set -euo pipefail

REPO="${1:?usage: drill.sh <owner/repo>}"
REGISTER_TIMEOUT_S=60    # dispatch -> run visible in the API (may queue behind a scan)
RUN_TIMEOUT_S=180        # run visible -> completed

latest_run_id() {
  gh run list --repo "$REPO" --workflow tripwires.yml \
    --event workflow_dispatch --limit 1 \
    --json databaseId --jq '.[0].databaseId // 0'
}

echo "==> firing all 8 wires in ONE run on $REPO (simulate=all)"
before=$(latest_run_id)
gh workflow run tripwires.yml --repo "$REPO" -f simulate=all

# wait for the new run to register
run_id=""
deadline=$((SECONDS + REGISTER_TIMEOUT_S))
while [ "$SECONDS" -lt "$deadline" ]; do
  sleep 3
  cur=$(latest_run_id)
  if [ "$cur" != "$before" ] && [ "$cur" != "0" ]; then run_id="$cur"; break; fi
done
if [ -z "$run_id" ]; then
  echo "FAIL: no run registered within ${REGISTER_TIMEOUT_S}s — inspect: gh run list --workflow tripwires.yml --repo $REPO" >&2
  exit 1
fi
echo "    run: https://github.com/$REPO/actions/runs/$run_id"

# wait for that run to complete
conclusion=""
deadline=$((SECONDS + RUN_TIMEOUT_S))
while [ "$SECONDS" -lt "$deadline" ]; do
  line=$(gh run view "$run_id" --repo "$REPO" --json status,conclusion \
    --jq '.status + " " + (.conclusion // "")')
  if [ "${line%% *}" = "completed" ]; then conclusion="${line#* }"; break; fi
  sleep 5
done

if [ "$conclusion" != "success" ]; then
  echo "FAIL: drill run ${conclusion:-timed out} (run $run_id) — inspect: gh run view $run_id --repo $REPO --log" >&2
  exit 1
fi

echo "==> PASS: drill run green (run $run_id)"
echo
echo "BINARY CHECKPOINT (a human answers yes/no):"
echo "  1. #ops shows exactly 3 [DRILL][P0] lines (red-main, panic, demo-freeze)?"
echo "  2. #feed shows exactly 5 [DRILL][P1] lines (stuck-pr, stale-claim, collision, deadlock, budget)?"
echo "If either answer is no: webhook secrets are missing/mis-wired — see docs/RUNBOOKS.md."
