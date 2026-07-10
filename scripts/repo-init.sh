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
#   TEAM_GH_USERS             teammate GitHub usernames, space-separated
#                             (optional — falls back to the source template's
#                             direct collaborators; never hardcoded in the repo)
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
  # Preserve any required_status_checks rule added later (enable-bot-gate.sh)
  # — a plain PUT of the base JSON silently clobbers it (observed live:
  # re-running repo-init dropped review/tests-touched from the merge gate).
  MERGED=$(gh api "repos/$REPO/rulesets/$EXISTING_ID" \
    | jq --argjson base "$RULESET_JSON" \
      '$base + {rules: ($base.rules + [.rules[]? | select(.type=="required_status_checks")])}')
  echo "$MERGED" | gh api --method PUT "repos/$REPO/rulesets/$EXISTING_ID" --input - >/dev/null
  echo "    updated existing ruleset ($EXISTING_ID) — required checks preserved"
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
  command -v jq >/dev/null || { echo "ERROR: jq required for webhook registration" >&2; exit 1; }
  echo "==> webhook: $WEBHOOK_URL"
  # Idempotent: skip if a hook already points at this URL (re-runs must not
  # stack duplicate hooks — every event would fan out N times).
  EXISTING_HOOKS=$(gh api "repos/$REPO/hooks" \
    --jq "[.[] | select(.config.url == \"$WEBHOOK_URL\")] | length" 2>/dev/null || echo 0)
  if [ "${EXISTING_HOOKS:-0}" -gt 0 ]; then
    echo "    already registered — skipped"
  else
    # NB: gh api -f/-F flag encoding 422s on this endpoint (mixed array/
    # boolean/nested keys) — build the payload as explicit JSON instead.
    jq -n --arg url "$WEBHOOK_URL" --arg secret "$TEAM_HEARTBEAT_SECRET" \
      '{name:"web", active:true,
        events:["issues","pull_request","push","label","issue_comment","workflow_run"],
        config:{url:$url, content_type:"json", secret:$secret}}' \
      | gh api --method POST "repos/$REPO/hooks" --input - >/dev/null
    echo "    registered"
  fi
else
  echo "==> webhook: skipped (no --webhook-url; add at D3 when the console deploys)"
fi

# --- 5. Team collaborators (usernames are setup input — never hardcoded) ------
# Priority: $TEAM_GH_USERS (space-separated, e.g. from ~/.hackathon-provision.env)
# → direct collaborators of the template this repo was generated from. The
# manager is whoever runs this script (the authenticated gh account) and is
# always excluded from invites.
echo "==> collaborators"
MANAGER_LOGIN=$(gh api user --jq .login)
echo "    manager: $MANAGER_LOGIN (authenticated gh account — not invited)"
TEAM_USERS="${TEAM_GH_USERS:-}"
if [ -n "$TEAM_USERS" ]; then
  echo "    source: \$TEAM_GH_USERS"
else
  TEMPLATE=$(gh api "repos/$REPO" --jq '.template_repository.full_name // empty' 2>/dev/null || true)
  if [ -n "$TEMPLATE" ]; then
    TEAM_USERS=$(gh api "repos/$TEMPLATE/collaborators?affiliation=direct" \
      --jq '.[].login' 2>/dev/null | grep -vx "$MANAGER_LOGIN" | tr '\n' ' ' || true)
    [ -n "${TEAM_USERS// /}" ] && echo "    source: template $TEMPLATE collaborators"
  fi
fi
if [ -z "${TEAM_USERS// /}" ]; then
  echo "    WARN: no teammates found — export TEAM_GH_USERS=\"<user1> <user2> <user3>\""
  echo "          (space-separated GitHub usernames) and rerun; invites are idempotent"
else
  for u in $TEAM_USERS; do
    [ "$u" = "$MANAGER_LOGIN" ] && continue
    if gh api -X PUT "repos/$REPO/collaborators/$u" -f permission=push >/dev/null 2>&1; then
      echo "    invited: $u (push) — they accept the email invite"
    else
      echo "    WARN: could not invite $u — check the username, then rerun"
    fi
  done
fi

echo "==> done: $REPO stamped"
echo "    verify protection: git push to main should be REJECTED"
