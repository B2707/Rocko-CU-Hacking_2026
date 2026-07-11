#!/usr/bin/env bash
# fm-build — headless, deterministic "issue -> open PR" for /fm (River) (P2).
#
# The unattended counterpart to interactive /consensus: claude builds in an
# isolated worktree, we push a NON-DRAFT PR and let CI + the review bot gate it.
# River NEVER merges — branch protection holds the PR for the manager's /fm ack.
# Idempotent: an issue already built this window, or with an open fm/<n>-*
# branch, is a no-op. Emits a machine-readable final line: FM-BUILD-RESULT {json}.
#
#   fm-build <issue#>
#
# Env: FM_BUILD_MODEL (default sonnet) · FM_BUILD_TIMEOUT seconds (default 1800).
set -euo pipefail

ISSUE="${1:?usage: fm-build <issue#>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_SH="$HERE/fm-state.sh"
REPO_ROOT="$(git rev-parse --path-format=absolute --git-common-dir | xargs dirname)"
MODEL="${FM_BUILD_MODEL:-sonnet}"
BUILD_TIMEOUT="${FM_BUILD_TIMEOUT:-1800}"
TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
BR=""

result()    { printf 'FM-BUILD-RESULT {"issue":%s,"status":"%s","branch":"%s","pr":%s}\n' "$ISSUE" "$1" "${2:-}" "${3:-null}"; }
die()       { echo "fm-build: $1" >&2; result "${2:-failed}" "$BR" null; exit "${3:-1}"; }
run_build() { if [ -n "$TIMEOUT_BIN" ]; then "$TIMEOUT_BIN" "$BUILD_TIMEOUT" "$@"; else "$@"; fi; }

command -v claude >/dev/null 2>&1 || die "claude CLI not installed" failed 1

meta="$(gh issue view "$ISSUE" --json number,title,body,state 2>/dev/null)" || die "issue #$ISSUE not found" failed 1
[ "$(echo "$meta" | jq -r '.state')" = "OPEN" ] || die "issue #$ISSUE is not OPEN" skipped 0

# --- idempotency: never double-build (state cache + live truth) ---
if bash "$STATE_SH" built? "$ISSUE" 2>/dev/null; then
  echo "fm-build: #$ISSUE already built this window — skip"; result skipped "" null; exit 0
fi
title="$(echo "$meta" | jq -r '.title')"
slug="$(printf '%s' "$title" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-40)"
BR="fm/$ISSUE-$slug"
git -C "$REPO_ROOT" fetch -q origin main
if git -C "$REPO_ROOT" ls-remote --exit-code --heads origin "fm/$ISSUE-*" "codex/$ISSUE-*" >/dev/null 2>&1; then
  echo "fm-build: a fm/$ISSUE-* or legacy codex/$ISSUE-* branch already exists on origin — skip"; result skipped "$BR" null; exit 0
fi

# --- isolated crewmate worktree off origin/main ---
wt="$TMP/wt"
git -C "$REPO_ROOT" worktree add -q "$wt" -b "$BR" origin/main || die "worktree/branch create failed" failed 1
cleanup_wt() { git -C "$REPO_ROOT" worktree remove --force "$wt" >/dev/null 2>&1 || true; }

# --- build prompt from the issue (stdin-file keeps the headless claude call clean and non-interactive) ---
{ cat <<EOF
Implement GitHub issue #$ISSUE in this repo. Follow existing repo conventions and
its scope. Write or adjust tests per the issue's acceptance criteria. Do NOT
expand scope beyond the issue. When done, summarize what you changed in one paragraph.
--- ISSUE #$ISSUE: $title ---
EOF
echo "$meta" | jq -r '.body // "(no description)"'; } > "$TMP/prompt.txt"

set +e
( cd "$wt" && run_build claude -p --model "$MODEL" --dangerously-skip-permissions < "$TMP/prompt.txt" > "$TMP/summary.txt" 2>"$TMP/build-err.txt" )
status=$?
set -e
if [ "$status" -ne 0 ] || [ ! -s "$TMP/summary.txt" ]; then
  cleanup_wt; die "claude build failed (exit $status) or empty summary — no PR opened ($(tail -c 300 "$TMP/build-err.txt" 2>/dev/null))" failed 1
fi

# --- commit whatever codex produced (it may or may not have committed) ---
git -C "$wt" add -A
ahead="$(git -C "$wt" log --oneline origin/main..HEAD 2>/dev/null || true)"
if git -C "$wt" diff --cached --quiet && [ -z "$ahead" ]; then
  cleanup_wt; echo "fm-build: codex produced no changes for #$ISSUE — no-op"; result no-op "$BR" null; exit 0
fi
git -C "$wt" diff --cached --quiet || git -C "$wt" commit -q -m "feat: implement #$ISSUE ($slug)

Built headlessly by /fm (River) via headless claude. Closes #$ISSUE.
$(cat "$TMP/summary.txt")"

# --- push + NON-DRAFT PR (drafts are skipped by CI + the review bot) ---
git -C "$wt" push -q -u origin "$BR" || { cleanup_wt; die "push failed" failed 1; }
REPO_NWO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh label create fm-built --repo "$REPO_NWO" --color BFD4F2 --description "Built headlessly by /fm (River)" 2>/dev/null || true
# stderr captured separately: gh writes progress there even on success, which would
# corrupt the FM-BUILD-RESULT JSON's pr field if merged into the captured URL
pr_url="$(gh pr create --repo "$REPO_NWO" --base main --head "$BR" \
  --title "[fm] #$ISSUE $title" \
  --body "Built headlessly by \`/fm\` (River) from issue #$ISSUE via \`headless claude\`.

$(cat "$TMP/summary.txt")

---
CI + the \`review\` bot gate this PR; the fm-merge engine (or your \`/fm ack\`) merges it. Closes #$ISSUE." \
  --label fm-built 2>"$TMP/pr-err.txt")" || { cleanup_wt; die "gh pr create failed: $(cat "$TMP/pr-err.txt")" failed 1; }

bash "$STATE_SH" mark-built "$ISSUE" >/dev/null 2>&1 || true
cleanup_wt
echo "fm-build: opened $pr_url"
result opened "$BR" "\"$pr_url\""
