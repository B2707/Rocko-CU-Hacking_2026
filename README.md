# hackathon-team-template

Team operating system for a 4-person hackathon team running Claude Code.
This repo is **pre-event tooling** — workflow scaffolding only. All project
code is written during the event in a fresh repo instantiated from this one.

## What this is

- **Kernel** (`CLAUDE.md`) — the team's working rules, loaded by every seat
- **Commands** (`.claude/commands/`) — `/doctor` `/start` `/ship` `/gotcha` `/propose`
- **Hooks** (`.claude/settings.json` + `scripts/hooks/`) — quality gates on every seat
- **Skills** (`.claude/skills/`) — project skill pack, auto-loaded from clone
- **Memory bank** (`data/context/`) — decisions, gotchas, instincts, handoffs
- **Automation** (`.github/workflows/`) — review bot, tripwires, gotcha-bot
- **Scripts** (`scripts/`) — `task` (command backend), `repo-init.sh` (instantiation)

## Quickstart (teammates)

```bash
git clone <this-repo> && cd <repo>
claude
/doctor        # verifies your seat: hooks firing, parity, versions
/start <N>     # take issue N: worktree + branch + brief loaded
/ship          # tests green -> PR + bot review; red -> draft PR
```

That's the whole interface. `/gotcha` records a lesson, `/propose` files an idea.

## Instantiating the event repo (hour zero)

GitHub copies **files only** — labels, branch protection, secrets, and webhooks
do not transfer. After creating the fresh event repo and pushing this
template's contents into it, stamp the settings:

```bash
scripts/repo-init.sh <owner>/<event-repo>
```

## Status

Build week in progress (D0 complete: repos + protection). Event ≈ Jul 14, 2026.

## Disclosure

This tooling repository was built before the event and contains no project
code. The event project's commit history begins at the event.
