---
description: Verify this seat is ready — auth, versions, hooks, config parity
allowed-tools: Bash
---
Run `./scripts/task doctor` and show the user the output verbatim.

If anything reports FAIL, explain the printed fix in one sentence and stop —
do not start work on a seat that is NOT READY. If all checks pass, confirm
"seat ready" and remind the user their next step is `/start <issue#>`.

(This is the per-seat preflight. To audit the harness itself — commands,
agents, skills, hooks, CI — against the Anthropic canon, use `/harness-audit`.)
