# DAY 0 — Hour Zero at the Venue

Budget: ~1h40m from doors-open to first dispatch. The whole team is present
as humans through Stage 3. Rehearsed once in the D5 drill.

| Clock | Stage | What happens |
|-------|-------|--------------|
| 0:00 | Inputs | Read event rules + tracks; fill in [`docs/COMPLIANCE.md`](./COMPLIANCE.md) (5-item rules checklist); EXTRACT THE JUDGING RUBRIC — criteria become the scoring frame for everything below |
| 0:10 | Generate | T2 runs parallel idea-gen agents seeded with tracks/rubric/team skills → 10–15 raw ideas |
| 0:25 | Kill fast | Per idea, 3 parallel filters — dies on failing 2 of 3: (a) product-lens "why" check, (b) has-it-been-done search (GitHub + past winners), (c) demo-wow: is the demo inherently captivating? → 2–3 finalists |
| 0:40 | Decide | Council (4-voice structured disagreement) on finalists; Bader + team make the human call (5-min-debate rule) → ONE idea + one named fallback |
| 0:50 | Scope + stack | MVP definition, golden path, acceptance criteria; stack → `stack.md`; run the stamp: `scripts/stack-stamp.sh` (agent-sort + rules-distill + project skills) |
| 1:10 | Docs + seed | PRD/architecture/task-list; decompose into the issue tree, REVIEWED AS ONE DOCUMENT by Bader; every issue tagged to a rubric criterion; lanes assigned to people |
| 1:40 | Dispatch | First slice = walking skeleton (golden path end-to-end, ugly is fine). Everyone `/start`s. |

## Event-repo instantiation (parallel with Stage 4–5)

GitHub carries FILES ONLY between repos — labels, protection, secrets, and
webhooks must be re-stamped:

```bash
gh repo create <owner>/<event-repo> --public
# push template contents:
git remote add event git@github.com:<owner>/<event-repo>.git && git push event main
# re-stamp settings (secrets read from Bader's terminal env):
scripts/repo-init.sh <owner>/<event-repo> --webhook-url <console-url>/api/webhook
# verify: a direct push to main must be REJECTED
```

## Standing rules born here
- `demo-path` label goes on every golden-path issue at seeding.
- The rubric mapping is the brief filter: an issue serving no criterion is
  `filler` at best.
- The demo owner seeds the `track:pitch` issue set now: demo video, portal
  form, presenter, T-90min prep block.
