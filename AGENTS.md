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

## Persistent-storage rule

- NEVER create or use a project clone, worktree, or primary working repository
  under `/tmp`, `/var/tmp`, `/private/tmp`, a `mktemp` directory, or any other
  automatically cleaned location.
- NEVER leave irreplaceable captures, manifests, fitted models, measurements,
  or other experiment artifacts only inside a temporary directory or an
  ignored directory of a temporary worktree.
- Use a persistent clone/worktree (for this machine,
  `~/Desktop/CU-hakcing-2026`) and store experimental artifacts under
  `${CU_HAKCING_DATA_DIR:-~/Desktop/CU-hakcing-captures}`. Temporary copies are
  allowed only as disposable caches after a persistent copy has been verified.
- Before deleting, replacing, or recloning any worktree, inventory its ignored
  files and copy every required artifact to persistent storage.
