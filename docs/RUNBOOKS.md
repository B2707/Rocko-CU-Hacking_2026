# Runbooks

## Build ladder (re-baselined 2026-07-08, event Tue Jul 14)

Honest scope ≈37–41h vs ~28–32 realistic hours → the cut line is decided NOW.
Claude-heavy days land Wed–Fri (manager's weekly window resets Saturday).

| Day | Date | Scope | Hours | Priority |
|-----|------|-------|-------|----------|
| D0 | Wed Jul 8 | Repos + protection canary + roles + rules check | 2 | MUST — ✅ done |
| D1 | Wed–Thu | Kernel, task script, 5 commands, memory bank, docs, hooks, judge-sim + submission-prep skills | 8 | MUST |
| D2 | Fri Jul 10 | Review bot (OAuth, hello-world verify), CI tests-touched, ruleset status check; gotcha-bot promote flow (timebox 2h), auto-unblock Action | 7 | MUST (bot+CI) / SHOULD (rest) |
| D3 | Sat Jul 11 | Console core: health strip + kanban + ticker, authed GET, lazy reconcile; Upstash provisioning | 6 | MUST (core) / COULD (burn+demo tiles) |
| D4 | Sun Jul 12 | Tripwires P0 wires + Discord + drill.sh (all 8 in 1 run), stack-stamp dry-run vs dummy repo, /pitch wrapper + knowledge distill | 6 | SHOULD (P0 wires ≈ must) |
| D5 | Mon Jul 13 | 90-min team drill (any-seat break-glass, Bader-gone P0, instantiation rehearsal, DAY0 dry-run) + fallout fixes + freeze | 4 | MUST |

**Cut order when hours vanish** (rightmost dies first):
review-bot → gotcha-bot promote flow → health strip → P0 tripwires ▮ CUT LINE ▮
kanban/ticker → auto-unblock → /pitch wrapper → burn/demo tiles → scripted P1
fires → full instinct plumbing.

## Red main (rollback — rehearsed at D5)
1. Announce in team channel: "main is red, reverting."
2. `gh pr list --state merged -L 3` → identify the breaking merge.
3. `git checkout -b revert/<sha> origin/main && git revert -m 1 <sha> && git push -u origin HEAD && gh pr create --fill` → merge via break-glass if the bot queue is slow.
4. Rerun the golden-path smoke. Then diagnose forward on a task branch.

## Seat capped (Pro quota hit — NORMAL, not an emergency)
1. Seat owner posts "capped" in the team channel; keeps working hands-on in the shell (tests, review, demo assets).
2. FM routes that lane's agent work to the manager Worker seat.
3. Check the reset clock; resume agent work when the window reopens.

## Wifi down
1. FM's pre-written next-up briefs are in `data/context/handoffs/` — work continues locally from those.
2. Verbal dispatch + whiteboard board. One named hotspot owner bridges for pushes only.
3. On reconnect: push branches, let webhooks replay, reconcile the board.

## Demo freeze (called by the demo owner, ~T-2h)
- Only `demo-path` + `break-glass` PRs merge. All other dispatches stop.
- Non-demo seats move to: pitch support, demo video, submission checklist, filler.
- The golden-path E2E recording doubles as the submission video.

## Break-glass (emergency bypass)
- Apply the `break-glass` label: review bot skips, CI gates to neutral.
- EVERY use is announced aloud + visible in the ticker. If you're reaching
  for it twice in an hour, stop and call Bader.

## Break-glass contacts
- **Vercel / Upstash / Discord / GitHub admin:** Bader (holds every root credential).
- **No standing deputy** (4-person event, deliberate): build-blocking P0s are
  self-serve — any seat can apply the `break-glass` label to merge, or run the
  red-main revert above. Bader-only items (secret rotation, console redeploy)
  are rare and off the build path; if Bader is unreachable the console degrades
  gracefully and the team keeps shipping via GitHub.
- Recovery fact: `TEAM_HEARTBEAT_SECRET` is recoverable via `vercel env pull`
  from the linked hackathon-console clone.

## Bring the review bot online (D2 verify — do these IN ORDER)
1. Mint: `claude setup-token` (manager's Max account).
2. Store, environment-gated: `gh secret set CLAUDE_CODE_OAUTH_TOKEN --env claude-bot --repo B2707/hackathon-team-template`
   (repo-init.sh creates the `claude-bot` environment; rerun it if missing).
3. Hello-world verify: open a trivial PR (e.g. touch `docs/hello.md`) → expect
   a bot comment on the PR and a green `review` check.
4. ONLY THEN: `scripts/enable-bot-gate.sh B2707/hackathon-team-template` —
   makes `review` + `tests-touched` required to merge into main. A required
   check that never reports blocks EVERY merge, so never skip step 3.
5. Break-glass check: apply the `break-glass` label to a test PR — the checks
   re-run as skipped (= green). That's the escape hatch working.

## Rotate a leaked secret
- `TEAM_HEARTBEAT_SECRET`: generate new → `gh secret set` on repo(s) → update console env in Vercel → all seats update `.env`.
- `CLAUDE_CODE_OAUTH_TOKEN`: `claude setup-token` again → `gh secret set`.
- Discord webhook URL: delete webhook in channel settings → recreate → update Actions secret.

## Teammate no-show
- FM merges the orphaned lane into the nearest lane at first standup; demo
  path re-scoped in the same standup. Issue tree is NOT re-seeded.

## Tripwires & drill (D4)

Scanner: `.github/workflows/tripwires.yml` → `scripts/tripwires.js`; runs
every 10 min plus instant paths (label events, pushes). P0 → #ops
(diagnose + fix-PR), P1 → #feed (notify). Requires the
`DISCORD_WEBHOOK_OPS` / `DISCORD_WEBHOOK_FEED` secrets (repo-init.sh stamps
them from env); without them it logs warnings and stays silent. Alerts
re-nag every pass while the condition persists — silence means fixed.

| Wire | Fires when | Tier |
|---|---|---|
| red-main | newest completed run of any workflow on main = failure | P0 |
| panic | `needs-human` label applied (instant) + queue non-empty (re-nag) | P0 |
| demo-freeze | any commit on main after `DEMO_FREEZE_AT` | P0 |
| stuck-pr | PR green-but-unmerged >30m, or review check absent/queued >15m (gate-health, audit C1) | P1 |
| stale-claim | assigned issue untouched >90m | P1 |
| collision | two open PRs touch the same file | P1 |
| deadlock | blocked-by cycle, or nothing ready/claimed/in-flight | P1 |
| budget | >10 review-bot runs in the last hour | P1 |

- **Panic button** = apply the `needs-human` label:
  `gh issue edit <N> --add-label needs-human --repo <repo>` (or the issue UI).
- **Demo freeze**: the demo owner calls it, then:
  `gh variable set DEMO_FREEZE_AT --body "2026-07-14T20:00:00Z" --repo <repo>`
  (UTC ISO timestamp; unset variable = tripwire dormant).
- **Drill** (deterministic, audit C2): `scripts/drill.sh <owner/repo>` fires
  all 8 wires through the REAL webhook path in a single run (`simulate=all`,
  `[DRILL]` prefix) and verifies that run is green. Binary checkpoint: #ops
  shows exactly 3 `[DRILL][P0]` lines, #feed exactly 5 `[DRILL][P1]` lines.
  Anything else = wiring broken; fix before the D5 team drill.

## First Mate / River loop (the manager's autonomous seat)

`/fm` on the First Mate pane is the standing loop (run it continuously with
`/loop 10m /fm`). Each tick: senses the board → triages candidates/proposals →
ships ready, fully-specified issues to **non-draft** PRs (`scripts/fm-build.sh`,
headless codex, isolated worktrees) → labels green + bot-passed ones `queued-merge`
→ **auto-merges the policy-eligible ones** (`scripts/fm-merge.sh`, rules below) →
overwrites `data/context/handoffs/DIGEST.md`. Code changes happen only in crewmate
worktrees; machinery merges stay human-only.

- **Rule-gated auto-merge (`scripts/fm-merge.sh`):** River merges `queued-merge` PRs
  itself — in dependency-priority order (Depends-on edges → demo-path > fix > feat >
  docs → oldest first), serially, only `mergeStateStatus=CLEAN` (a green-but-BEHIND PR
  is updated from main and re-validated next tick — the ruleset's strict mode is off, so
  this is what prevents two green PRs from breaking each other). Merges are SHA-pinned
  to the assessed head and labels re-verified at merge time (the panic button always
  wins); ≤3 update-branch attempts per PR per window, then `needs-human`. **Machinery PRs never
  auto-merge:** anything touching `.github/`, `.claude/`, `scripts/`, `.env*` waits for
  you, as do `needs-human` / `break-glass` / `PLAN:` items and everything during demo
  freeze. Caps: `FM_MERGE_TICK_CAP` (2/tick), `FM_MERGE_CAP` (8/UTC-day).
- **Morning ack (audit + human tier):** `/fm ack` shows what River merged
  (`fm-state get '.mergedPRs'`), the current merge plan (`fm-merge assess`), and the
  HUMAN-tier queue — those you merge yourself (`gh pr merge <n> --squash`).
- **Merge kill-switch:** `FM_AUTOMERGE=off` (queue-only, no merges) or
  `touch data/context/fm/PAUSE` (halts builds AND merges).
- **Snapshot any time:** `/fm bearings` (read-only "where are we").
- **Build budget:** `FM_BUILD_BUDGET` (default 2/tick); River builds 0 while the
  `budget` tripwire is hot. Manager seat only (guarded by `TEAM_SEAT` / `FM_MANAGER`).
- **If River misbehaves:** it cannot merge or push main by construction. To pause it,
  `touch data/context/fm/PAUSE` (halts builds; triage continues), stop the loop (Ctrl-C
  the `/loop`), or clear `queued-merge` labels. PRs it left are harmless — review or close.

### Unattended-River hardening (P2 — bonus, never a dependency)

River is safe to leave running overnight; if codex or the loop is flaky it just stops
building and keeps triaging — the manager can always dispatch by hand instead.

- **Per-tick gate** (`scripts/fm-precheck.sh`): builds only when codex is authed, the night
  cap isn't hit, the `budget` wire is cool, and no PAUSE file — else the tick is triage-only.
- **Headless builds** (`scripts/fm-build.sh <n>`): deterministic issue→non-draft-PR via
  `codex exec` in an isolated worktree; the loop uses this instead of interactive `/consensus`.
- **Night cap:** `FM_NIGHT_BUILD_CAP` (default 8) builds per UTC-day window (auto-resets daily).
- **Kill-switch:** `touch data/context/fm/PAUSE` pauses all builds; `rm` it to resume.
- **Restart-proof:** state lives in `data/context/fm/state.json` (a cache — the live repo is the
  source of truth) so a `/loop` context reset never double-builds an issue.
