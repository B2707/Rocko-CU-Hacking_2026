# Codex agents in this repo (headless machinery)

You are invoked headlessly — by `/fm` (scripts/fm-build.sh) or `/consensus`
from the manager seat. The prompt you received IS the task spec; follow it
exactly. This file adds only the repo's hard rules.

- NEVER push to main and NEVER merge anything. Work only on the branch you
  were given (`codex/*` or `task/*`). PRs are gated server-side (CI + review
  bot + ruleset) — your job ends at a pushed branch.
- NEVER edit machinery paths: `.github/`, `.claude/`, `scripts/`, `.env*`.
  If the task seems to require it, stop and say so in your summary instead.
- One issue = one worktree = one branch. Stay inside the working directory
  you were launched in; never touch sibling worktrees.
- Never print or commit secrets (tokens, webhook URLs, `.env` values).
- Tests accompany code — the `tests-touched` gate fails PRs that change
  source without touching tests (label `test-exempt` only via the brief).
- Keep diffs minimal and scoped to the issue. Flag scope creep, don't do it.
