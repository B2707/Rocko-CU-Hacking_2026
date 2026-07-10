#!/usr/bin/env bash
# tripwire-kicker — GitHub deprioritizes */10 cron on free repos (measured real
# cadence: ~2-3 HOURS between sweeps). This kicker dispatches the tripwires
# sweep every 10 minutes so red-main/stuck-pr/stale-claim alerts arrive on the
# cadence the thresholds were designed for. Run it on the manager's OPS pane
# for the duration of the event; Ctrl-C to stop. Harmless to double-run
# (the workflow's concurrency group serializes overlapping sweeps).
set -euo pipefail
NWO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
echo "kicking tripwires.yml on $NWO every 600s — Ctrl-C to stop"
while true; do
  gh workflow run tripwires.yml -R "$NWO" >/dev/null 2>&1 \
    || echo "dispatch failed at $(date +%H:%M:%S) — will retry next cycle"
  sleep 600
done
