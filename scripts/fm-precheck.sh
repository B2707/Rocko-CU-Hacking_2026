#!/usr/bin/env bash
# fm-precheck — per-tick gate for /fm (River) Phase 3 (P2). Decides whether this
# tick may BUILD or must degrade to triage-only. Prints one line; exit 0 = build.
# Fail-safe: any doubt → triage-only (nonzero). River is a bonus, never a
# dependency — when this says TRIAGE-ONLY the loop still senses/triages/digests.
#
#   BUILD-OK      → exit 0
#   TRIAGE-ONLY   → exit 1  (+ reason)
#
# Signals: PAUSE kill-switch · codex auth · night build cap (FM_NIGHT_BUILD_CAP,
# default 8) · review-bot budget (>10 claude-review runs in the last hour).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_SH="$HERE/fm-state.sh"
CAP="${FM_NIGHT_BUILD_CAP:-8}"

if bash "$STATE_SH" paused? 2>/dev/null; then
  echo "TRIAGE-ONLY: PAUSE kill-switch set (rm data/context/fm/PAUSE to resume builds)"; exit 1
fi
if ! command -v codex >/dev/null 2>&1 || ! codex login status >/dev/null 2>&1; then
  echo "TRIAGE-ONLY: codex unavailable/unauthenticated (run: codex login)"; exit 1
fi
bash "$STATE_SH" init >/dev/null 2>&1 || true
builds="$(bash "$STATE_SH" get '.buildsThisWindow' 2>/dev/null || echo 0)"
if [ "${builds:-0}" -ge "$CAP" ]; then
  echo "TRIAGE-ONLY: night build cap reached ($builds/$CAP — raise FM_NIGHT_BUILD_CAP or /fm ack)"; exit 1
fi
runs="$(gh run list --workflow claude-review.yml --limit 40 --json createdAt \
  -q '[.[] | select(.createdAt > (now - 3600 | todate))] | length' 2>/dev/null || echo 0)"
if [ "${runs:-0}" -gt 10 ]; then
  echo "TRIAGE-ONLY: review-bot budget hot ($runs runs in the last hour)"; exit 1
fi
echo "BUILD-OK: codex authed · builds $builds/$CAP · review-bot ${runs:-0}/hr"
