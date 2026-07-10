#!/usr/bin/env bash
# Flip the review bot + CI to REQUIRED status checks on the protect-main
# ruleset. Run ONLY after the hello-world verify PR shows green runs for
# "review", "tests-touched", "build-test", and "hooks-test" — a required check
# that never reports blocks every merge (see docs/RUNBOOKS.md "Bring the review bot online").
#
# Usage: scripts/enable-bot-gate.sh <owner/repo>
set -euo pipefail
REPO="${1:?usage: enable-bot-gate.sh <owner/repo>}"

ruleset_id=$(gh api "repos/$REPO/rulesets" --jq '.[] | select(.name=="protect-main") | .id')
if [ -z "$ruleset_id" ]; then
  echo "ERROR: protect-main ruleset not found on $REPO (run scripts/repo-init.sh first)" >&2
  exit 1
fi

gh api "repos/$REPO/rulesets/$ruleset_id" | jq '{
  name, target, enforcement, conditions,
  rules: ((.rules // [])
    | map(select(.type != "required_status_checks"))
    + [{
        type: "required_status_checks",
        parameters: {
          strict_required_status_checks_policy: false,
          required_status_checks: [{context: "review"}, {context: "tests-touched"}, {context: "build-test"}, {context: "hooks-test"}]
        }
      }])
}' | gh api -X PUT "repos/$REPO/rulesets/$ruleset_id" --input - >/dev/null

echo "OK: 'review' + 'tests-touched' + 'build-test' + 'hooks-test' are now required to merge into main on $REPO"
echo "Verify: a fresh PR must show all four checks before the merge button goes green."
