---
description: Record a lesson the team should know (quarantined candidate)
allowed-tools: Bash
---
Run `./scripts/task gotcha $ARGUMENTS`.

If no argument was given, first compose the lesson yourself in ONE line:
what surprised you + what to do instead ("X fails when Y — do Z instead").
Candidates are quarantined and ride this branch's PR; the First Mate acks
them into shared memory. Severity is not your call — record and continue.
Only exception: if the hazard is active for someone RIGHT NOW (breaks main,
blocks the demo, others will hit it within the hour), also add the
`team:triage` label to your current issue so the Triage seat wakes.
