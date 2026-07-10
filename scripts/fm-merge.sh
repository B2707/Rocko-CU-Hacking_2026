#!/usr/bin/env bash
# fm-merge — rule-gated auto-merge engine for /fm (River).
#
# River may merge, but ONLY through this script, ONLY PRs queued with the
# `queued-merge` label, and ONLY within the policy below. Branch protection
# still enforces the required checks server-side — this policy layers on top
# of the gate, never routes around it. Adversarially verified (4-lens panel);
# every state/API failure path fails CLOSED (no merge), never open.
#
#   fm-merge assess     print the merge plan (order + verdict per PR); read-only
#   fm-merge            execute the plan: serial merge train, caps enforced
#
# POLICY:
#   H1 machinery is human-only  — diffs touching .github/ .claude/ scripts/ .env*
#                                 never auto-merge (River can't grow its own
#                                 permissions or alter the gate). File list comes
#                                 from `gh pr diff --name-only` (COMPLETE — the
#                                 --json files field truncates at 100 and would
#                                 let a buried scripts/ file slip through);
#                                 unfetchable list → HUMAN (fail-closed).
#   H2 label/title outs         — needs-human, break-glass, PLAN:-titles (case/
#                                 whitespace-normalized) → human
#   S1 freeze                   — DEMO_FREEZE_AT set & past → zero auto-merges;
#                                 an unreadable variable or offset-less timestamp
#                                 is treated as FROZEN (fail-safe)
#   S2 caps                     — FM_MERGE_TICK_CAP (2)/tick, FM_MERGE_CAP (8)/UTC-day;
#                                 unreadable state → refuse to merge (fail-closed)
#   S3 kill-switch              — data/context/fm/PAUSE or FM_AUTOMERGE=off → none
#   C1 freshness (CRITICAL)     — ruleset strict mode is OFF, so GitHub would merge
#                                 a green-but-BEHIND PR validated against OLD main.
#                                 River refuses: only CLEAN/UNSTABLE merge; BEHIND →
#                                 update-branch (≤3/window, then needs-human) + defer
#                                 a tick so CI re-validates; DIRTY → needs-human.
#   C2 TOCTOU                   — merges are pinned to the ASSESSED head SHA
#                                 (--match-head-commit) and labels are re-verified
#                                 immediately before merging (panic button wins).
#
# ORDER (the merge priority River assesses):
#   1. dependencies  — "Depends-on: #12, #13" in the PR body (ALL refs); unmerged → defer
#   2. priority      — demo-path 100 > fix/hotfix 50 > feat 30 > other 20 > docs/chore 10
#                      ([fm] #N prefixes stripped before scoring)
#   3. age           — older PR first on ties
#   Serial train: one merge per step, then main has moved — everything else goes
#   BEHIND and is updated + re-validated before its turn. Never batch on stale checks.
set -euo pipefail

MODE="${1:-merge}"                                    # assess | merge
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_SH="$HERE/fm-state.sh"
TICK_CAP="${FM_MERGE_TICK_CAP:-2}"
WINDOW_CAP="${FM_MERGE_CAP:-8}"
PLAN=""; LOCKD=""
cleanup() { [ -n "$PLAN" ] && rm -f "$PLAN"; [ -n "$LOCKD" ] && rmdir "$LOCKD" 2>/dev/null || true; }
trap cleanup EXIT

say() { printf 'FM-MERGE %s\n' "$*"; }

# --- S3: kill-switches ---
[ "${FM_AUTOMERGE:-on}" = "off" ] && { say "OFF: FM_AUTOMERGE=off — queue only, no merges"; exit 0; }
bash "$STATE_SH" paused? 2>/dev/null && { say "OFF: PAUSE kill-switch set"; exit 0; }
gh auth status >/dev/null 2>&1 || { say "OFF: gh not authenticated"; exit 1; }
NWO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
# ensure our labels exist (idempotent — repo-init predates /fm and never stamped them)
gh label create queued-merge --repo "$NWO" --color 0E8A16 --description "Green + queued for the fm-merge engine" 2>/dev/null || true
gh label create needs-human  --repo "$NWO" --color D93F0B --description "Panic button: a human must decide"    2>/dev/null || true

# --- S1: demo freeze — fail-SAFE: API error or ambiguous timestamp = frozen ---
ERRF="$(mktemp)"
if ! FREEZE="$(gh variable get DEMO_FREEZE_AT 2>"$ERRF")"; then
  if grep -qi 'not found' "$ERRF"; then FREEZE=""; else
    rm -f "$ERRF"; say "OFF: cannot read DEMO_FREEZE_AT (API error) — fail-safe, no merges"; exit 0
  fi
fi
rm -f "$ERRF"
if [ -n "$FREEZE" ]; then
  if command -v node >/dev/null 2>&1; then
    # frozen when: past the timestamp, unparseable, OR a date-time with no explicit
    # Z/offset (Date.parse would read it as the runner's LOCAL zone — ambiguous on
    # demo day, so we refuse to guess). Date-only strings parse as UTC and are fine.
    node -e 's=process.argv[1];hasTZ=/(Z|[+-]\d{2}:?\d{2})$/.test(s)||!/T/.test(s);t=Date.parse(s);process.exit(!hasTZ||isNaN(t)||Date.now()>=t?0:1)' "$FREEZE" \
      && { say "OFF: demo freeze (DEMO_FREEZE_AT=$FREEZE; active, unparseable, or missing Z/offset) — humans + break-glass only"; exit 0; }
  else
    say "OFF: DEMO_FREEZE_AT set but node missing to parse it — fail-safe, no merges"; exit 0
  fi
fi

# --- S2: window cap — unreadable state = fail-closed ---
bash "$STATE_SH" init >/dev/null 2>&1 || { say "OFF: state init failed — fail-safe (rm data/context/fm/state.json to reset)"; exit 1; }
merged_window="$(bash "$STATE_SH" get '.mergesThisWindow // 0' 2>/dev/null)" || merged_window=""
case "$merged_window" in ''|*[!0-9]*) say "OFF: state unreadable — fail-safe (rm data/context/fm/state.json to reset)"; exit 1;; esac
[ "$merged_window" -ge "$WINDOW_CAP" ] && { say "OFF: window cap reached ($merged_window/$WINDOW_CAP)"; exit 0; }

# --- engine mutex: two racing trains would jointly exceed caps + double-update PRs ---
FM_DIR="$(dirname "$(bash "$STATE_SH" path)")"; mkdir -p "$FM_DIR"
LOCKD="$FM_DIR/merge.lock"
if ! mkdir "$LOCKD" 2>/dev/null; then
  if [ -n "$(find "$LOCKD" -mmin +30 2>/dev/null)" ]; then rmdir "$LOCKD" 2>/dev/null || true; mkdir "$LOCKD" 2>/dev/null || { LOCKD=""; say "OFF: could not take merge lock"; exit 0; }
  else LOCKD=""; say "OFF: another fm-merge run holds the lock"; exit 0; fi
fi

# poll transient UNKNOWN (GitHub recomputes mergeability lazily after main moves)
fetch_mss() {
  local i s
  for i in 1 2 3; do
    s="$(gh pr view "$1" --repo "$NWO" --json mergeStateStatus -q .mergeStateStatus 2>/dev/null)" || { echo FETCH_FAIL; return 0; }
    [ "$s" != "UNKNOWN" ] && { echo "$s"; return 0; }
    sleep 5
  done
  echo UNKNOWN
}

# --- collect queued candidates (search-lagged; each PR is re-verified fresh below) ---
QUEUE="$(gh pr list --repo "$NWO" --label queued-merge --state open --json number -q '.[].number')"
[ -z "$QUEUE" ] && { say "queue empty — nothing to do"; exit 0; }
N_QUEUED="$(echo "$QUEUE" | wc -l | tr -d ' ')"

# --- classify + score each PR ---
PLAN="$(mktemp)"
for n in $QUEUE; do
  pr="$(gh pr view "$n" --repo "$NWO" --json number,title,body,labels,createdAt,isDraft,mergeStateStatus,headRefOid 2>/dev/null)" \
    || { say "  #$n: fetch failed — skipping this tick"; continue; }
  # sanitize: titles are teammate-controlled input; a literal tab/newline would forge plan records
  title="$(echo "$pr" | jq -r .title | tr '\t\r\n' '   ')"
  labels="$(echo "$pr" | jq -r '[.labels[].name] | join(",")')"
  mss="$(echo "$pr" | jq -r .mergeStateStatus)"
  sha="$(echo "$pr" | jq -r .headRefOid)"
  verdict="MERGE"; why="clean"

  # fresh-label truth beats the lagged search index: de-queued PRs must not merge
  case ",$labels," in *,queued-merge,*) : ;; *) verdict="SKIP"; why="queued-merge label gone (search-index lag)";; esac
  # H2: label/title outs (title normalized — case + leading whitespace)
  case ",$labels," in *,needs-human,*) verdict="HUMAN"; why="needs-human label";; esac
  case ",$labels," in *,break-glass,*) verdict="HUMAN"; why="break-glass is human-only";; esac
  t_norm="$(printf '%s' "$title" | sed 's/^[[:space:]]*//' | tr '[:upper:]' '[:lower:]')"
  case "$t_norm" in plan:*|plan\ :*) verdict="HUMAN"; why="PLAN: title — a plan change is the manager's call";; esac
  # H1: machinery paths — COMPLETE file list (--json files truncates at 100); fail-closed
  if [ "$verdict" = "MERGE" ]; then
    if ! flist="$(gh pr diff "$n" --repo "$NWO" --name-only 2>/dev/null)" || [ -z "$flist" ]; then
      verdict="HUMAN"; why="cannot enumerate changed files — fail-closed to human"
    elif echo "$flist" | grep -qE '^(\.github/|\.claude/|scripts/|\.env)'; then
      verdict="HUMAN"; why="touches machinery (.github/.claude/scripts/.env) — human-only tier"
    fi
  fi
  # C1: freshness / mergeability
  if [ "$verdict" = "MERGE" ]; then
    [ "$mss" = "UNKNOWN" ] && mss="$(fetch_mss "$n")"
    case "$mss" in
      CLEAN)    : ;;
      UNSTABLE) why="required checks green; NOTE: a non-required check is red (hooks-test?) — see digest";;
      BEHIND)   verdict="REBASE"; why="green but validated against old main — update from main + re-validate next tick";;
      DIRTY)    verdict="CONFLICT"; why="merge conflict with main";;
      *)        verdict="WAIT"; why="mergeStateStatus=$mss";;
    esac
  fi
  # deps: ALL "Depends-on: #12, #13 and #14" refs must already be merged
  if [ "$verdict" = "MERGE" ]; then
    deps="$(echo "$pr" | jq -r '.body // ""' | grep -oiE 'depends[- ]on[: ]+(#[0-9]+[[:space:],and]*)+' | grep -oE '#[0-9]+' | tr -d '#' | sort -u || true)"
    for d in $deps; do
      dstate="$(gh pr view "$d" --repo "$NWO" --json state -q .state 2>/dev/null || echo NOT-A-PR)"
      [ "$dstate" = "MERGED" ] || { verdict="DEFER"; why="depends on #$d ($dstate, not merged)"; break; }
    done
  fi
  # priority score ([fm] #N prefix stripped so River's own fixes rank as fixes)
  score_t="$(printf '%s' "$title" | tr '[:upper:]' '[:lower:]')"
  case "$score_t" in \[fm\]\ \#*) score_t="${score_t#\[fm\] \#}"; score_t="${score_t#* }";; esac
  prio=20
  case ",$labels," in
    *,demo-path,*) prio=100;;
    *) case "$score_t" in fix*|hotfix*) prio=50;; feat*) prio=30;; docs*|chore*) prio=10;; esac;;
  esac
  created="$(echo "$pr" | jq -r .createdAt)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$prio" "$created" "$n" "$sha" "$verdict" "$why" "$title" >> "$PLAN"
done

# --- ordered plan: priority desc, then oldest first ---
ORDERED="$(sort -t"$(printf '\t')" -k1,1nr -k2,2 "$PLAN")"
say "plan ($N_QUEUED queued, order = priority desc then age):"
echo "$ORDERED" | while IFS=$'\t' read -r prio created n sha verdict why title; do
  say "  #$n [$prio] $verdict — $why — $title"
done
[ "$MODE" = "assess" ] && exit 0

# --- serial merge train ---
merged_tick=0
while IFS=$'\t' read -r prio created n sha verdict why title; do
  case "$n" in ''|*[!0-9]*) continue;; esac                      # belt: numeric PR numbers only
  [ "$merged_tick" -ge "$TICK_CAP" ] && { say "tick cap reached ($merged_tick/$TICK_CAP) — rest defer to next tick"; break; }
  [ "$merged_window" -ge "$WINDOW_CAP" ] && { say "window cap reached — stop"; break; }
  case "$verdict" in
    MERGE)
      # C2 TOCTOU: re-verify labels at merge time (panic button applied mid-train wins)
      labels_now="$(gh pr view "$n" --repo "$NWO" --json labels -q '[.labels[].name]|join(",")' 2>/dev/null)" \
        || { say "  #$n: label re-check failed — defer"; continue; }
      case ",$labels_now," in
        *,needs-human,*|*,break-glass,*) say "  #$n: needs-human/break-glass applied mid-train — skipping"; continue;;
        *,queued-merge,*) : ;;
        *) say "  #$n: de-queued mid-train — skipping"; continue;;
      esac
      mss_now="$(fetch_mss "$n")"
      if [ "$mss_now" != "CLEAN" ] && [ "$mss_now" != "UNSTABLE" ]; then
        say "  #$n went $mss_now after an earlier merge — update from main + defer (C1)"
        att="$(bash "$STATE_SH" mark-rebase "$n" 2>/dev/null || echo 99)"
        if [ "$att" -gt 3 ] 2>/dev/null; then
          gh pr edit "$n" --repo "$NWO" --add-label needs-human >/dev/null 2>&1 || true
          say "  #$n: update-branch churn cap ($att) — labeled needs-human"
        else
          gh pr update-branch "$n" --repo "$NWO" >/dev/null 2>&1 || say "  #$n update-branch failed — will retry next tick"
        fi
        continue
      fi
      # C2: pin to the assessed SHA — a head pushed after assessment cannot merge
      if gh pr merge "$n" --repo "$NWO" --squash --match-head-commit "$sha" 2>/dev/null; then
        merged_tick=$((merged_tick+1))
        if new_count="$(bash "$STATE_SH" mark-merged "$n" 2>/dev/null)"; then merged_window="$new_count"; else
          say "  STATE WRITE FAILED after merging #$n — halting train (cap integrity)"; break
        fi
        say "  MERGED #$n ($title) — $merged_tick this tick, $merged_window/$WINDOW_CAP window"
      else
        # reconcile: client error ≠ server refusal — a sleep/network drop mid-call can hide a real merge
        st="$(gh pr view "$n" --repo "$NWO" --json state -q .state 2>/dev/null || echo UNKNOWN)"
        if [ "$st" = "MERGED" ]; then
          merged_tick=$((merged_tick+1))
          new_count="$(bash "$STATE_SH" mark-merged "$n" 2>/dev/null)" && merged_window="$new_count" \
            || { say "  STATE WRITE FAILED after merging #$n — halting train"; break; }
          say "  MERGED #$n (client error, server succeeded)"
        else
          say "  #$n merge refused (head moved since assess, or server gate) — re-assess next tick"
        fi
      fi
      ;;
    REBASE)
      att="$(bash "$STATE_SH" mark-rebase "$n" 2>/dev/null || echo 99)"
      if [ "$att" -gt 3 ] 2>/dev/null; then
        gh pr edit "$n" --repo "$NWO" --add-label needs-human >/dev/null 2>&1 || true
        say "  #$n: update-branch churn cap ($att this window) — labeled needs-human (CI never re-greens?)"
      else
        gh pr update-branch "$n" --repo "$NWO" >/dev/null 2>&1 \
          && say "  #$n updated from main (merge commit) — CI re-validates, merges next tick" \
          || say "  #$n update-branch failed (likely conflict) — will show DIRTY next tick"
      fi
      ;;
    CONFLICT)
      gh pr edit "$n" --repo "$NWO" --add-label needs-human >/dev/null 2>&1 || true
      say "  #$n CONFLICT with main → labeled needs-human"
      ;;
    HUMAN|DEFER|WAIT|SKIP)
      say "  #$n left for ${verdict} — $why"
      ;;
  esac
done <<< "$ORDERED"
say "done: merged $merged_tick this tick ($merged_window/$WINDOW_CAP window)"
