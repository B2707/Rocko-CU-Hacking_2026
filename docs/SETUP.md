# Seat Setup (5 minutes)

## You need
- Claude Code installed, signed into YOUR OWN Claude account (Pro or Max —
  never a shared account)
- `gh` CLI authenticated (`gh auth login`)
- node ≥ 20
- `codex` CLI for `/consensus` (`npm i -g @openai/codex`, then `codex login`)

## Steps

```bash
git clone git@github.com:B2707/<repo>.git && cd <repo>
cp .env.example .env        # fill values Bader sends you — never commit .env
export TEAM_SEAT=<yourname> # sjp / amr / adham (add to your shell profile)
claude
```

First launch: Claude Code asks you to **trust this project's hooks — approve
once**. Then:

```
/doctor
```

Fix anything it flags (it tells you how). When it says READY:

```
/start <issue#>   # take a task
/ship             # when done
```

That's the whole job. `/gotcha` when something burns you, `/propose` when
you spot work outside your brief.

## First Mate (River)
- `/fm` is the manager's autonomous loop (`/loop 10m /fm`); `/fm bearings` is
  the read-only status snapshot.
- River builds ready, fully-specified issues to **non-draft** PRs, then
  auto-merges the policy-eligible green ones in dependency-priority order.
- PRs touching `.github/`, `.claude/`, `scripts/`, or `.env*` NEVER
  auto-merge — humans only.
- Kill switches: `touch data/context/fm/PAUSE` halts builds + merges;
  `FM_AUTOMERGE=off` keeps builds on and turns merges off.

## Pro-seat rules (you're on Claude Pro)
- ONE hot agent terminal; your second terminal is a plain shell (dev server,
  logs) — never a second agent.
- If you hit your usage cap: tell the team channel, flip to hands-on coding
  and testing in your shell; your lane's agent work routes to the manager's
  Worker seat. This is normal, not an emergency.
- Go light on Claude the weekend before the event.
