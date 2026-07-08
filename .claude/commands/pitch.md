---
description: Build the pitch — deck narrative + demo script timing (anyone runs it; demo owner has final call)
---

Build or refine the pitch for this project.

1. Load `.claude/skills/pitchdeck/SKILL.md` and
   `.claude/skills/pitch-kit/knowledge/DISTILLED.md` (the one-page sheet).
   Open the full pitch-kit knowledge files only when a specific section
   needs depth — the distilled sheet covers the operating rules.
2. Inputs come from the repo, not from memory: the judging rubric extracted at
   Day-0 Stage 1, the golden-path demo flow (issues labeled `demo-path`), and
   `stack.md`.
3. Produce the deck per the pitchdeck skill's output format, using
   `.claude/skills/pitch-kit/templates/pitchdeck-outline.md` as the skeleton.
4. Demo timing rules (hard):
   - The wow moment lands before 60% of demo runtime has elapsed — aim for 40%.
   - Every spoken line is 15 words or fewer.
   - Narrate every loading state. The only silence is the deliberate 2–3s pause
     AFTER the wow moment.
5. Write results to `docs/pitch/deck.md` and `docs/pitch/script.md` on a task
   branch and ship as a PR (`./scripts/task ship`).

Ownership: anyone can run this and draft. The demo owner (roster in CLAUDE.md)
has final call on `docs/pitch/` and the demo freeze. Before submission,
`/judge-sim` must pass on the final deck.

$ARGUMENTS
