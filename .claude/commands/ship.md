---
description: Ship the current task — rebase, verify, open PR (draft if red)
allowed-tools: Bash
---
Run `./scripts/task ship` from the task worktree and show the user the output.

The script rebases on origin/main, runs build + tests if they exist, scans
the diff for committed secrets, and opens the PR with a Verification block:
- GREEN → real PR; the review bot takes it from here. Tell the user the PR
  URL and that they may take ONE more ready issue while it's in review.
- RED → draft PR only. Summarize exactly what failed and fix it before
  converting. Never mark a draft ready without a green rerun.
- REBASE CONFLICT → resolve the conflict with the user, then rerun.
