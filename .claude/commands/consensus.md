---
description: Plan with the planning model, reach consensus with Codex (≤5 rounds), Codex executes, then cross-model review of the diff
argument-hint: <feature or task description>
allowed-tools: Bash, Read, Write
---

# /consensus — cross-model plan → execute → review

*Based on ECC multi-plan/multi-execute/model-route + santa-loop codex patterns.*

The planning model and Codex argue a plan to consensus, **Codex writes the code**,
then the planning model reviews the diff cross-model. One session, four phases,
hard caps throughout. Extends ECC's plan→consensus→execute→audit loop, swapping the
executor from Claude/`codeagent-wrapper` to the verified `codex exec` CLI (0.142.5).

## Model tier (align with `/model-route`)

- **Default — Opus.** Run this command from an **Opus** session for normal PR-level
  work: Opus plans, judges the consensus loop, and reviews the diff.
- **Escalation — Fable.** Only reach for **Fable** on architecture-scale or original
  ("senior") issues — big/greenfield design, cross-cutting refactors, ambiguous scope.
- **Execution — always Codex.** The Claude session (Opus or Fable) **never writes
  production code** here. Codex critiques (read-only) and implements (workspace-write).
  This inverts ECC multi-execute's "Claude is the only writer" rule on purpose.

## Core Protocols

- **Language Protocol** — English to the tools/models; reply to the user in their language.
- **Model Discipline** — the planning model plans/judges/reviews; Codex critiques + executes. No exceptions.
- **Stop-Loss / Hard Caps** — consensus loop ≤ 5 rounds; post-review fix loop ≤ 1 extra Codex pass. Never exceed.
- **Sandbox Discipline** — Codex-as-critic runs `--sandbox read-only`; Codex-as-executor runs `--sandbox workspace-write`. Never give the critic write access.
- **Branch Safety** — execution only on a clean tree, only on a fresh `codex/<slug>` branch. Never push unless the user asks.

## Codex invocation reference (verified — codex-cli 0.142.5, ChatGPT auth)

The prompt goes in via **stdin from a file** (santa-loop pattern). The `- < FILE`
form supplies the prompt AND closes stdin at EOF, which avoids the documented
`codex exec` background-stdin hang (`Reading additional input from stdin...`). If you
ever pass an inline prompt string instead, append `< /dev/null`.

- **Critic (read-only):**
  `codex exec --sandbox read-only -m gpt-5.4 -C "$(pwd)" -o "$TMP/out.txt" - < "$TMP/prompt.txt"`
- **Executor (workspace-write):**
  `codex exec --sandbox workspace-write -m gpt-5.4 -C "$(pwd)" -o "$TMP/out.txt" - < "$TMP/prompt.txt"`

Flags: `-s/--sandbox` {read-only | workspace-write | danger-full-access} · `-m/--model`
· `-C/--cd` working root · `-o/--output-last-message FILE` captures the final message
only (clean token/summary capture) · `--json` streams JSONL events if you need them.
`-m gpt-5.4` matches santa-loop; drop `-m` to use the installed default (gpt-5.5) or bump it.
`workspace-write` disables network by default — if execution must fetch/install, add
`-c sandbox_workspace_write.network_access=true`.

Set up a scratch dir once:
```bash
TMP="$(mktemp -d)"
```

## Execution Workflow

**Task:** $ARGUMENTS

### Phase 0 — Preflight  `[Mode: Preflight]`

Codex is both the critic and the executor — this command is inert without it.
Verify it is installed AND authenticated before doing anything else:
```bash
command -v codex >/dev/null 2>&1 || { echo "STOP: codex CLI not found — install it (npm i -g @openai/codex), then run 'codex login' (see docs/SETUP.md)"; exit 1; }
codex login status >/dev/null 2>&1 || { echo "STOP: codex is installed but not authenticated — run 'codex login', then rerun /consensus"; exit 1; }
```
If either check fails, STOP and tell the user exactly which command to run. Do
not fall through to planning — every later phase depends on Codex.

### Phase 1 — Plan  `[Mode: Plan]`

The planning model drafts a tight implementation plan for **$ARGUMENTS**.
- If scope is fuzzy, sharpen it first (run the grill-me skill if available, else ask the user 2–3 clarifying questions).
- Plan format (keep under 60 lines): **goal · constraints · files to touch · step list · test plan · risks**.
- Write it to `$TMP/plan.md`.

### Phase 2 — Consensus loop with Codex  `[Mode: Consensus]`  (max 5 rounds)

Repeat up to **5** times:
1. Ensure the current plan is saved to `$TMP/plan.md`.
2. Build the critic prompt and run Codex as an adversarial critic (read-only):
   ```bash
   { cat <<'EOF'
   You are an adversarial staff engineer reviewing an implementation plan.
   Critique it strictly: correctness, missing steps, hidden complexity, simpler
   alternatives, risks. Inspect the repo (read-only) to check the plan against real
   code. If the plan is sound and you have NO material objection, reply with a single
   line containing exactly: CONSENSUS
   Otherwise DO NOT write CONSENSUS — return a numbered list of concrete objections,
   most important first.
   --- PLAN ---
   EOF
   cat "$TMP/plan.md"; } > "$TMP/critic-prompt.txt"

   codex exec --sandbox read-only -m gpt-5.4 -C "$(pwd)" \
     -o "$TMP/critique.txt" - < "$TMP/critic-prompt.txt"
   status=$?
   if [ "$status" -ne 0 ] || [ ! -s "$TMP/critique.txt" ]; then
     echo "ERROR: codex critic failed (exit $status) or returned empty output."
     echo "Surface this to the user and STOP — never treat a failed/empty critique as CONSENSUS."
     exit 1
   fi
   ```
3. If the critique is standalone consensus, break the loop (only reachable when
   the critic ran cleanly and produced output — the guard above already bailed
   on any failure or empty file):
   ```bash
   grep -qx 'CONSENSUS' "$TMP/critique.txt" && echo "CONSENSUS REACHED"
   ```
4. Otherwise the planning model judges each objection — **accept** (revise the plan)
   or **rebut** (record why) — rewrites `$TMP/plan.md`, and continues.

After 5 rounds without consensus: present both positions (the planning model's plan vs
Codex's outstanding objections) to the user and **STOP**. Do not execute.

### Phase 3 — Execute  `[Mode: Execute]`  (Codex, never the Claude session)

Preconditions — abort if unmet:
```bash
[ -z "$(git status --porcelain)" ] || { echo "working tree not clean — commit/stash first"; exit 1; }
BASE="$(git rev-parse HEAD)"                        # remember the review base
SLUG="<kebab-slug-from-$ARGUMENTS>"
git switch -c "codex/$SLUG"
```
Hand the AGREED plan to Codex in workspace-write, cwd = repo root:
```bash
{ cat <<'EOF'
Implement exactly this agreed plan in the current repo. Follow existing repo
conventions. Write or adjust tests per the plan's test plan. Do NOT expand scope
beyond the plan. When done, summarize what you changed.
--- AGREED PLAN ---
EOF
cat "$TMP/plan.md"; } > "$TMP/exec-prompt.txt"

codex exec --sandbox workspace-write -m gpt-5.4 -C "$(pwd)" \
  -o "$TMP/exec-summary.txt" - < "$TMP/exec-prompt.txt"
status=$?
if [ "$status" -ne 0 ] || [ ! -s "$TMP/exec-summary.txt" ]; then
  echo "ERROR: codex executor failed (exit $status) or produced no summary — surface this, never assume the code landed."
fi
```
Report Codex's summary (`$TMP/exec-summary.txt`). If Codex fails mid-way (nonzero
exit or empty summary as flagged above), report the state; **retry at most
once**, then stop and hand back to the user.

### Phase 4 — Review  `[Mode: Review]`  (planning model, cross-model)

- `git diff --stat "$BASE"...HEAD`, then read the full diff.
- Fresh-eyes review against the agreed plan: correctness, security, tests actually
  touched, scope creep. **Verdict-first: PASS or CHANGES-NEEDED** + numbered findings.
- If **CHANGES-NEEDED**: write the numbered fix list to `$TMP/fix-prompt.txt` and send it
  back to Codex — **one** more workspace-write exec — then re-review **once**.
  ```bash
  codex exec --sandbox workspace-write -m gpt-5.4 -C "$(pwd)" \
    -o "$TMP/fix-summary.txt" - < "$TMP/fix-prompt.txt"
  ```
- Finish: run the repo's test suite if present; report results. Leave the branch ready
  for PR. **Do NOT push unless the user asked.**

## Key Rules

1. **The Claude session never writes production code** — it plans/judges/reviews; Codex executes.
2. **Right tier for the job** — Opus by default; Fable only for senior/architecture-scale planning.
3. **Hard caps are hard** — 5 consensus rounds, 1 post-review fix pass, then stop.
4. **Sandbox by phase** — read-only for critique, workspace-write for execution.
5. **Clean tree, fresh branch** — never execute on a dirty tree or an existing branch.
6. **No surprise pushes** — the branch is left ready; pushing/PR is the user's call.
7. **Prompts via stdin file** (`- < FILE`) — closes stdin, dodges the codex background hang.

## Arguments

`$ARGUMENTS` — the feature or task to plan, build, and review. Fuzzy scope is
sharpened in Phase 1 before any Codex round.

## Usage

```
/consensus add a rate limiter to the /submit endpoint
/consensus refactor the auth middleware to drop the deprecated cookie path
```
