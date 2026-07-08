#!/usr/bin/env bash
# repo-init.sh — stamp the GitHub settings that cloning/template-generation
# does NOT carry: labels, main-branch protection ruleset, Actions secrets,
# and (optionally) the console webhook.
#
# Usage:
#   scripts/repo-init.sh <owner/repo> [--webhook-url URL] [--skip-secrets]
#
# Secrets are read from the CALLING ENVIRONMENT and never appear in the repo:
#   CLAUDE_CODE_OAUTH_TOKEN   review bot auth (required for bot at D2+)
#   TEAM_HEARTBEAT_SECRET     console heartbeat auth (required at D3+)
#   DISCORD_WEBHOOK_OPS       P0 alert channel (required at D4+)
#   DISCORD_WEBHOOK_FEED      P1 ticker channel (required at D4+)
# Unset vars are skipped with a warning — rerun any time; every step is
# idempotent.
set -euo pipefail

REPO="${1:?usage: repo-init.sh <owner/repo> [--webhook-url URL] [--skip-secrets]}"
shift

WEBHOOK_URL=""
SKIP_SECRETS=false
while [ $# -gt 0 ]; do
  case "$1" in
    --webhook-url) WEBHOOK_URL="${2:?--webhook-url needs a value}"; shift 2 ;;
    --skip-secrets) SKIP_SECRETS=true; shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

echo "==> repo-init: $REPO"

# --- 1. Labels (idempotent via --force) --------------------------------------
stamp_label() { # name color description
  gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force >/dev/null
  echo "    label: $1"
}
echo "==> labels"
stamp_label "team:triage"  "D93F0B" "Wakes the Triage Worker (T3)"
stamp_label "proposed"     "C5DEF5" "Quarantined idea from /propose — FM triages"
stamp_label "ready"        "0E8A16" "Unblocked and dispatchable — renders on the board"
stamp_label "blocked"      "B60205" "Waiting on a blocker issue — hidden from Ready"
stamp_label "demo-path"    "FBCA04" "On the golden path — outranks nice-to-haves"
stamp_label "break-glass"  "000000" "Emergency bypass — bot skips, CI gates to neutral, loud ticker"
stamp_label "test-exempt"  "BFD4F2" "Brief explicitly waives tests-touched guard"
stamp_label "filler"       "EDEDED" "Gap-stuffing pool: polish/tests/docs/demo assets"
stamp_label "needs-human"  "5319E7" "Escalated past the envelope — a human must decide"

# --- 2. Branch protection ruleset (public-repo path, free tier) --------------
# PRs required into the default branch; deletions and force-pushes blocked;
# zero required approvals (the review bot lands as a required status check at
# D2 — add it to this ruleset then). Applies to admins too: empty bypass list.
echo "==> ruleset: protect-main"
EXISTING_ID=$(gh api "repos/$REPO/rulesets" --jq '.[] | select(.name=="protect-main") | .id' 2>/dev/null || true)
RULESET_JSON=$(cat <<'JSON'
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      }
    }
  ]
}
JSON
)
if [ -n "$EXISTING_ID" ]; then
  echo "$RULESET_JSON" | gh api --method PUT "repos/$REPO/rulesets/$EXISTING_ID" --input - >/dev/null
  echo "    updated existing ruleset ($EXISTING_ID)"
else
  echo "$RULESET_JSON" | gh api --method POST "repos/$REPO/rulesets" --input - >/dev/null
  echo "    created"
fi

# --- 3. Bot environment + Actions secrets (from env; values never logged) ----
# The claude-bot environment gates the OAuth token: only jobs declaring
# `environment: claude-bot` (the review workflow) can read it.
echo "==> environment: claude-bot"
gh api -X PUT "repos/$REPO/environments/claude-bot" >/dev/null
echo "    created/verified"

if [ "$SKIP_SECRETS" = true ]; then
  echo "==> secrets: skipped (--skip-secrets)"
else
  echo "==> secrets (from env)"
  stamp_secret() { # var-name
    local name="$1"
    if [ -n "${!name:-}" ]; then
      printf '%s' "${!name}" | gh secret set "$name" --repo "$REPO"
      echo "    set: $name"
    else
      echo "    WARN: \$$name not in env — skipped (rerun after exporting it)"
    fi
  }
  if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
    printf '%s' "$CLAUDE_CODE_OAUTH_TOKEN" | gh secret set CLAUDE_CODE_OAUTH_TOKEN --env claude-bot --repo "$REPO"
    echo "    set: CLAUDE_CODE_OAUTH_TOKEN (environment: claude-bot)"
  else
    echo "    WARN: \$CLAUDE_CODE_OAUTH_TOKEN not in env — skipped (rerun after exporting it)"
  fi
  stamp_secret TEAM_HEARTBEAT_SECRET
  stamp_secret DISCORD_WEBHOOK_OPS
  stamp_secret DISCORD_WEBHOOK_FEED
fi

# --- 4. Console webhook (optional until the console exists, D3+) -------------
if [ -n "$WEBHOOK_URL" ]; then
  if [ -z "${TEAM_HEARTBEAT_SECRET:-}" ]; then
    echo "ERROR: --webhook-url requires TEAM_HEARTBEAT_SECRET in env (HMAC secret)" >&2
    exit 1
  fi
  echo "==> webhook: $WEBHOOK_URL"
  gh api --method POST "repos/$REPO/hooks" \
    -f name=web \
    -F active=true \
    -f 'events[]=issues' -f 'events[]=pull_request' -f 'events[]=push' \
    -f 'events[]=label' -f 'events[]=issue_comment' -f 'events[]=workflow_run' \
    -f config.url="$WEBHOOK_URL" \
    -f config.content_type=json \
    -f config.secret="$TEAM_HEARTBEAT_SECRET" >/dev/null
  echo "    registered"
else
  echo "==> webhook: skipped (no --webhook-url; add at D3 when the console deploys)"
fi

echo "==> done: $REPO stamped"
echo "    verify protection: git push to main should be REJECTED"
