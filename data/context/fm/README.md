# `data/context/fm/` — First Mate / River durable state (P2)

Restart-proof state for the `/fm` (River) loop. **The live repo is the source of
truth; the files here are only a cache** — if they vanish, River re-derives what
it already built from open `codex/*` branches and `fm-built` PRs, so a lost state
file degrades to a re-scan (never a double-merge — branch protection — and rarely
a double-build — `fm-build`'s branch-collision check).

| File | Tracked? | What it is |
|---|---|---|
| `README.md` | ✅ committed | this doc |
| `state.json` | ✖ gitignored | `{schema:2, window, buildsThisWindow, mergesThisWindow, tick, builtIssues[], mergedPRs[], rebaseAttempts{}}` — window counters + idempotency cache; **`mergedPRs` is append-only across windows (the audit trail)**; corrupt file = mutations fail closed, `rm` it to reset (`scripts/fm-state.sh`) |
| `PAUSE` | ✖ gitignored | kill-switch: if present, River holds **all builds AND merges** (triage/scout/digest continue) |
| `.lock/`, `merge.lock/` | ✖ gitignored | mkdir mutexes (state writes / the merge train); stale ones self-clear (5 min / 30 min) |

- **Night build cap:** `FM_NIGHT_BUILD_CAP` (default 8) per UTC-day window; the
  window auto-resets on a new day.
- **Pause River builds:** `touch data/context/fm/PAUSE` → resume: `rm data/context/fm/PAUSE`.
- Managed by `scripts/fm-state.sh`, gated by `scripts/fm-precheck.sh`, consumed by
  `scripts/fm-build.sh`. See `.claude/commands/fm.md` and `docs/RUNBOOKS.md`.
