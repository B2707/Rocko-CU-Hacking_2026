---
description: Audit this repo's harness (commands, agents, skills, hooks, CI, CLAUDE.md, MCP) against the Anthropic canon — dispatches the workflow-doctor agent, read-only, cited
---

Launch the **workflow-doctor** subagent in AUDIT mode over this repository (use
the Task tool with subagent_type `workflow-doctor`). Give it this explicit
hand-off:

- **Mode:** AUDIT — enumerate every harness surface FIRST (don't sample), then
  check each against the mapped canon principle.
- **Scope:** this repo's harness — `.claude/` (commands, agents, skills,
  `settings.json`), `scripts/` + `scripts/hooks/`, `.github/workflows/`,
  `CLAUDE.md`, `.mcp.json` (if present), and `data/context/` memory hygiene.
- **Rulebook:** the Anthropic canon in `data/context/anthropic-canon/` — read
  `index.md` first; every finding must cite its canon entry.

Relay the agent's full report to the user verbatim — findings ranked
most-severe-first, clean areas, obstacles, and the PASS / WARN / BLOCK verdict.

For a live mid-hackathon workflow failure instead (the review bot flags
everything, subagents finish but leave gaps, a hook lets an action through,
structured output is malformed), tell the agent "INCIDENT mode" and describe
the symptom.

Note: this is the harness/workflow auditor. For a per-seat readiness preflight
(auth, versions, hook parity), use `/doctor`.

$ARGUMENTS
