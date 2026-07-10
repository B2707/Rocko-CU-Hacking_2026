#!/usr/bin/env bash
# fm-state — durable, restart-proof state for the /fm (River) loop (P2).
#
# The LIVE REPO is the source of truth; this file is only a cache. If it is
# lost, River re-derives "already built" from open codex/* branches + fm-built
# PRs, so a lost state file degrades to a re-scan — never a double-merge (branch
# protection) and rarely a double-build (fm-build's branch-collision check).
# If state.json is CORRUPT, mutations fail loudly (fail-closed) — `rm` it to reset.
#
#   fm-state path                 print the state file path
#   fm-state init                 ensure state exists; reset the window on a new UTC day; bump tick
#   fm-state get <jq-filter>      read a value, e.g.  fm-state get '.buildsThisWindow'
#   fm-state built? <issue#>      exit 0 if the issue was already built this window
#   fm-state mark-built <issue#>  record a build: append the issue + bump the window counter
#   fm-state mark-merged <pr#>    record an auto-merge; echoes the NEW window count
#                                 (mergedPRs is APPEND-ONLY across windows — it is the audit trail)
#   fm-state mark-rebase <pr#>    count an update-branch attempt; echoes the NEW per-PR count
#                                 (fm-merge caps rebase churn; resets each window)
#   fm-state paused?              exit 0 if the PAUSE kill-switch file exists
#
# Concurrency: mutations take an mkdir spin-lock (flock doesn't exist on stock
# macOS) and every write is mktemp + jq-validated + atomic mv — two racing /fm
# instances can no longer tear the file or lose increments.
set -euo pipefail

REPO_ROOT="$(git rev-parse --path-format=absolute --git-common-dir | xargs dirname)"
FM_DIR="$REPO_ROOT/data/context/fm"
STATE="$FM_DIR/state.json"
PAUSE="$FM_DIR/PAUSE"
LOCK="$FM_DIR/.lock"
TODAY="$(date -u +%F)"
HAVE_LOCK=0

_unlock() { [ "$HAVE_LOCK" = 1 ] && rmdir "$LOCK" 2>/dev/null || true; }
trap _unlock EXIT

_lock() {  # spin up to ~10s, then steal locks older than 5 min (crashed holder)
  mkdir -p "$FM_DIR"
  local i=0
  until mkdir "$LOCK" 2>/dev/null; do
    i=$((i+1))
    if [ "$i" -gt 50 ]; then
      if [ -n "$(find "$LOCK" -mmin +5 2>/dev/null)" ]; then rmdir "$LOCK" 2>/dev/null || true; continue; fi
      echo "fm-state: lock timeout ($LOCK)" >&2; return 1
    fi
    sleep 0.2
  done
  HAVE_LOCK=1
}

_write() {  # stdin -> validated atomic install; corrupt JSON never lands
  mkdir -p "$FM_DIR"
  local tmp; tmp="$(mktemp "$FM_DIR/.state.XXXXXX")"
  cat > "$tmp"
  if jq -e . "$tmp" >/dev/null 2>&1; then mv -f "$tmp" "$STATE"; else
    rm -f "$tmp"; echo "fm-state: refusing to write invalid JSON (state intact)" >&2; return 1
  fi
}

_ensure() {
  mkdir -p "$FM_DIR"
  [ -f "$STATE" ] || printf '{"schema":2,"window":"%s","buildsThisWindow":0,"mergesThisWindow":0,"tick":0,"builtIssues":[],"mergedPRs":[],"rebaseAttempts":{}}\n' "$TODAY" | _write
  local win; win="$(jq -r '.window // ""' "$STATE" 2>/dev/null || echo "")"
  if [ "$win" != "$TODAY" ]; then
    # new UTC day → reset window counters; mergedPRs stays (append-only audit)
    jq --arg d "$TODAY" '.window=$d | .buildsThisWindow=0 | .mergesThisWindow=0 | .builtIssues=[] | .rebaseAttempts={}' "$STATE" | _write
  fi
}

cmd="${1:-init}"; shift || true
case "$cmd" in
  path)       echo "$STATE" ;;
  init)       _lock; _ensure; jq '.tick=(.tick+1)' "$STATE" | _write ;;
  get)        _ensure; jq -r "${1:?usage: fm-state get <jq-filter>}" "$STATE" ;;
  built?)     _ensure; jq -e --argjson n "${1:?usage: fm-state built? <issue#>}" '.builtIssues | index($n) != null' "$STATE" >/dev/null ;;
  mark-built) _lock; _ensure; jq --argjson n "${1:?usage: fm-state mark-built <issue#>}" '.builtIssues=(.builtIssues+[$n]|unique) | .buildsThisWindow=(.buildsThisWindow+1)' "$STATE" | _write ;;
  mark-merged) _lock; _ensure
    jq --argjson n "${1:?usage: fm-state mark-merged <pr#>}" '.mergedPRs=((.mergedPRs//[])+[$n]|unique) | .mergesThisWindow=((.mergesThisWindow//0)+1)' "$STATE" | _write
    jq -r '.mergesThisWindow' "$STATE" ;;
  mark-rebase) _lock; _ensure
    jq --arg k "${1:?usage: fm-state mark-rebase <pr#>}" '.rebaseAttempts=((.rebaseAttempts//{}) + {($k): (((.rebaseAttempts//{})[$k] // 0) + 1)})' "$STATE" | _write
    jq -r --arg k "$1" '.rebaseAttempts[$k]' "$STATE" ;;
  paused?)    [ -f "$PAUSE" ] ;;
  *)          echo "fm-state: unknown subcommand: $cmd" >&2; exit 2 ;;
esac
