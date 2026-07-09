---
description: Simulate the judge panel against the current pitch + demo (pre-submission check)
---

Run a judge simulation against the current state of the pitch and demo.

1. Load `.claude/skills/judge-simulator/SKILL.md` and
   `.claude/skills/pitch-kit/knowledge/DISTILLED.md` (the one-page sheet).
   Open the full pitch-kit knowledge files only when a specific axis needs
   depth.
2. Build the panel from the ACTUAL event rubric (Day-0 Stage 1 extraction).
   Only fall back to `pitch-kit/knowledge/judging-criteria.md` typical weights
   if no rubric has been extracted yet — and say so in the output.
3. Evaluate `docs/pitch/` and the golden-path demo flow. Produce: adversarial
   questions with rebuttals, critical objections, predicted 1–5 scores per
   axis, and the top 3 fixes ranked by expected score impact.
4. PRE-SUBMISSION CHECK (advisory — a prose reminder, not a hard gate:
   submission happens on an external platform the harness can't intercept):
   run this against the FINAL deck and demo before the team submits. If any
   axis predicts 2 or lower, flag it to Bader and the demo owner explicitly —
   never silently pass.

$ARGUMENTS
