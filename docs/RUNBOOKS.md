# Runbooks

## Build ladder (re-baselined 2026-07-08, event Tue Jul 14)

Honest scope ≈37–41h vs ~28–32 realistic hours → the cut line is decided NOW.
Claude-heavy days land Wed–Fri (manager's weekly window resets Saturday).

| Day | Date | Scope | Hours | Priority |
|-----|------|-------|-------|----------|
| D0 | Wed Jul 8 | Repos + protection canary + roles + rules check | 2 | MUST — ✅ done |
| D1 | Wed–Thu | Kernel, task script, 5 commands, memory bank, docs, hooks, judge-sim + submission-prep skills | 8 | MUST |
| D2 | Fri Jul 10 | Review bot (OAuth, hello-world verify), CI tests-touched, ruleset status check; gotcha-bot promote flow (timebox 2h), auto-unblock Action | 7 | MUST (bot+CI) / SHOULD (rest) |
| D3 | Sat Jul 11 | Console core: health strip + kanban + ticker, authed GET, lazy reconcile; Upstash provisioning; deputy Vercel access | 6 | MUST (core) / COULD (burn+demo tiles) |
| D4 | Sun Jul 12 | Tripwires P0 wires + Discord + drill.sh (8/8 fires), stack-stamp dry-run vs dummy repo, /pitch wrapper + knowledge distill | 6 | SHOULD (P0 wires ≈ must) |
| D5 | Mon Jul 13 | 90-min team drill (deputy break-glass, Bader-gone P0, instantiation rehearsal, DAY0 dry-run) + fallout fixes + freeze | 4 | MUST |

**Cut order when hours vanish** (rightmost dies first):
review-bot → gotcha-bot promote flow → health strip → P0 tripwires ▮ CUT LINE ▮
kanban/ticker → auto-unblock → /pitch wrapper → burn/demo tiles → night-batch
launcher → scripted P1 fires → full instinct plumbing.

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
  all 8 wires through the REAL webhook path with a `[DRILL]` prefix and
  verifies 8/8 runs green. Binary checkpoint: #ops shows exactly 3
  `[DRILL][P0]` lines, #feed exactly 5 `[DRILL][P1]` lines. Anything else =
  wiring broken; fix before the D5 team drill.
