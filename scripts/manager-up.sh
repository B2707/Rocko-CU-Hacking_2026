#!/usr/bin/env bash
# manager-up.sh — bring up Bader's manager cockpit in one tmux session.
#
# Layout (main-vertical):
#   ┌────────────────────────┬────────────────────────────┐
#   │  🧭 ORCHESTRATOR       │  ⚓ FIRST MATE (River)      │
#   │  (you work here)       │  auto-runs /loop 10m /fm   │
#   │  planning · /consensus ├────────────────────────────┤
#   │                        │  🛠  OPS (plain shell)      │
#   └────────────────────────┴────────────────────────────┘
#
# Codex note: /consensus runs INSIDE the Orchestrator pane — codex is a one-shot
# subprocess it spawns, not a separate terminal. No extra pane needed by default.
#
# Usage:
#   scripts/manager-up.sh [repo-path] [session-name]
#   scripts/manager-up.sh                       # defaults to ~/hackathon-team-template
#   scripts/manager-up.sh ~/event-repo          # event cockpit — gets its OWN session
#
# Each repo gets its own session (hq-<repo>), so the event cockpit never
# collides with the template one. Re-running attaches. Works from a plain
# terminal or from inside tmux (switch-client). Detach: Ctrl-b d.
set -euo pipefail

REPO="${1:-$HOME/hackathon-team-template}"
command -v tmux >/dev/null 2>&1 || { echo "tmux not installed — run: brew install tmux"; exit 1; }
[ -d "$REPO" ] || { echo "repo path not found: $REPO"; exit 1; }
REPO="$(cd "$REPO" && pwd)"
[ -x "$REPO/scripts/task" ] || { echo "not the team repo (no scripts/task): $REPO — pass the repo path"; exit 1; }
SESSION="${2:-hq-$(basename "$REPO")}"
# TEAM_SEAT: /fm's manager-seat guard needs it in EVERY pane.
# ECC_SKIP_PREPUSH: the ECC global pre-push hook (installed by the Codex/ECC
# integration on this machine) runs lint+typecheck+test+build on every push —
# pure duplication of the server-side CI gate, and it would throttle every
# River push. Skip it in cockpit panes; the pre-commit secret scan still runs.
SEAT="export TEAM_SEAT=B2707 ECC_SKIP_PREPUSH=1"

attach() { if [ -n "${TMUX:-}" ]; then tmux switch-client -t "$SESSION"; else exec tmux attach -t "$SESSION"; fi; }

# Already up? Just attach (per-repo session names make this always the right one).
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already running — attaching. (others: tmux ls)"
  attach; exit 0
fi

# If setup dies mid-build, remove the half-built session so re-runs start clean.
trap 'tmux kill-session -t "$SESSION" 2>/dev/null || true; echo "manager-up failed — partial session removed" >&2' ERR

# Model routing (Bader): Opus = planner/executor tier for both agent panes;
# /model fable manually for senior/original planning moments. Explicit models
# always — panes must never inherit whatever the default happens to be.
# --dangerously-skip-permissions (Bader 2026-07-10): the cockpit is unattended
# by design; permission prompts would stall River overnight. Guardrails stay
# server-side (ruleset, review bot, machinery-paths rule, one-writer hook).

# Pane 0 — Orchestrator (you): planning + /consensus (codex executes in-pane)
tmux new-session -d -s "$SESSION" -n hq -c "$REPO"
tmux send-keys -t "$SESSION:hq.0" \
  "$SEAT; clear; printf '🧭 ORCHESTRATOR — planning · /consensus (codex runs here)\n\n'; claude --model opus --dangerously-skip-permissions" C-m

# Pane 1 — First Mate (River): AUTO-STARTS the loop. First-ever run on a fresh
# clone: approve the folder-trust prompt once, then the loop flows.
tmux split-window -h -t "$SESSION:hq" -c "$REPO"
tmux send-keys -t "$SESSION:hq.1" \
  "$SEAT; clear; printf '⚓ FIRST MATE (River) — auto /loop 10m /fm · morning: /fm ack · pause: touch data/context/fm/PAUSE\n\n'; claude --model opus --dangerously-skip-permissions '/loop 10m /fm'" C-m

# Pane 2 — Ops: plain shell (git, gh, drills, tripwire kicker) — NO agent.
# Also starts the manager presence beat (console seat panel) in the background.
tmux split-window -v -t "$SESSION:hq.1" -c "$REPO"
tmux send-keys -t "$SESSION:hq.2" \
  "$SEAT; clear; printf '🛠  OPS — plain shell · during the event run: bash scripts/tripwire-kicker.sh\n\n'; (bash scripts/heartbeat.sh --loop 300 >/dev/null 2>&1 &)" C-m

tmux select-layout -t "$SESSION:hq" main-vertical
tmux select-pane -t "$SESSION:hq.0"
trap - ERR
attach
