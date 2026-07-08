# Team OS Kernel

You are one seat in a 4-person hackathon team. GitHub is the team's nervous
system; this file is law on every seat. When in doubt: smallest correct step,
then escalate through the channels below.

## The team

- **Bader** — manager: First Mate dispatcher (T1), orchestrator (T2), triage
  (T3), night batch (T4), ops shell (T5). Escalations end at Bader.
- **sjp** — teammate lane; currently holds the **deputy + demo owner** roles
  (final call on demo freeze + submission). Roles are reassignable — the
  role matters, not the name.
- **Amr**, **Adham** — teammate lanes.

Teammate seats run ONE hot agent terminal + one plain shell. Model floor: Sonnet.

## The five commands (the whole interface)

- `/doctor` — seat health. Run at session start; never work on a NOT READY seat.
- `/start N` — take issue N: worktree + branch + Task Brief + team memory.
- `/ship` — rebase → verify → PR (draft if red). Green PRs get the review bot.
- `/gotcha` — record a lesson (quarantined candidate; FM promotes).
- `/propose` — file an idea (quarantined issue; FM triages).

Pitch track — anyone runs these; the demo owner has final call: `/pitch`
builds the deck + demo script; `/judge-sim` stress-tests it against the
rubric and is required before submission.

## Hard rules (enforced by hooks and the server; violations bounce)

1. NEVER push to main. No exceptions — not even the manager. PRs only.
2. NEVER create issues with `gh issue create` — `/propose` is the only door.
3. Stay inside your Task Brief's file scope. Out-of-brief discovery →
   `/propose`, then return to the brief. No silent fixes. No scope creep.
4. Tests are part of the task when the brief names them (the brief IS the
   test spec). Red tests = draft PR only.
5. Secrets never enter the repo. `.env` is gitignored; `${ENV_VAR}`
   placeholders only in committed config.
6. One writer per memory surface: `gotchas.md` = FM/bot only; `decisions/` =
   one file per decision via PR; you write only into `*-candidates/`.

## Agent duties (reflexes, not suggestions)

- **AUTO-GOTCHA**: anything that cost >10 minutes or would bite a teammate —
  run `/gotcha` BEFORE continuing.
- **AUTO-PROPOSE**: any out-of-brief discovery — `/propose`, back to brief.
- Severity routing — you pick the CHANNEL, never the outcome:
  - G1 note → `/gotcha` (nobody interrupted)
  - G2 active hazard → `/gotcha` + add `team:triage` label to your issue
  - G3 fire (main red / demo / deploy) → tripwires page the manager; say it loudly too
  - P1 idea → `/propose` · P2 lane-relevant → `/propose` + mention the FM
  - P3 plan change (tool swap, feature add/cut, rescope) → `/propose` with a
    "PLAN:" title — routes to Bader, always.

## Working style

- **K1**: while your PR is in bot review you may take ONE more ready issue. Never two.
- `demo-path` outranks everything else in the Ready column.
- Blocked? Comment what you tried on the issue, add `team:triage`, take a
  `filler` issue. A stuck human is a P0 — the FM will notice or be told.
- `data/context/` is the team brain. `/start` loads what you need; do not
  paste whole memory files into context.

## Escalation ends at humans

Agents never decide outcomes for plan changes, tool swaps, guardrail edits,
or disputes — those land in front of Bader (`needs-human` label / Discord).
The review bot's verdict stands unless a human overrides with `break-glass`.
