# Anthropic Agentic-Workflows Canon

The team's grounded evidence base for how agentic workflows, harness config,
tools/MCP, prompting, review bots, and context/cost are *supposed* to be built.
Every claim here is distilled in our own words from Anthropic's Claude Certified
Architect (CCA-F) concept library; no verbatim course prose is reproduced. Each
bullet ends with the source page URL in parens so a finding can be traced back.

- **Source sites:** https://www.anthropiccertifications.com/learn (concept
  library, 44 pages, distilled 2026-07-08) and
  https://www.anthropiccertifications.com/courses (5 courses / ~105 lessons —
  Claude Code 101, Intro to MCP, Intro to Subagents, Intro to Agent Skills, and
  the CCA-F Foundations course; new-material lessons distilled 2026-07-09 over
  two passes — the second closing the remaining CCA-F architect, Intro to
  Subagents, Intro to Agent Skills, and Claude Code 101 deltas).
  The CCA-F course lessons are enriched supersets of the /learn concept cards
  (same task statements, deeper mechanics); the four intro courses are
  hierarchies /learn does not cover at all. Intro to MCP *protocol internals*
  (JSON-RPC framing, transport lifecycle, capability negotiation) are
  deliberately out of scope — they don't bear on auditing this harness; only the
  MCP config/scoping/resources material relevant to the harness is distilled.
- **Distilled:** 2026-07-08 (/learn), extended 2026-07-09 (/courses, two passes)
- **Who uses this:** the `workflow-doctor` agent (`.claude/agents/workflow-doctor.md`)
  reads these files as its rulebook — AUDIT mode checks the repo against them,
  INCIDENT mode diagnoses live problems against them. Any teammate can read them
  directly too.

## How to cite from this canon

When the doctor (or anyone) makes a recommendation, cite the backing entry as:

> `(canon: <file>.md — <source URL>)`

If the canon does not cover a situation, say so explicitly rather than inventing
a rule. Silence of the canon is itself a finding.

## The five CCA-F domains (study/effort weighting)

The exam — and this canon — is organized into five domains. Weights signal how
much of agentic-workflow practice each area represents (https://www.anthropiccertifications.com/learn):

1. **Agentic Architecture & Orchestration — 27%** (largest): agentic loops,
   multi-agent / coordinator-subagent, hooks, task decomposition, sessions.
2. **Claude Code Configuration & Workflows — 20%**: CLAUDE.md hierarchy, skills
   & commands, path-specific rules, plan mode, iterative refinement, CI/CD.
3. **Prompt Engineering & Structured Output — 20%**: explicit criteria,
   few-shot, JSON-schema output, validation loops, batch, multi-instance review.
4. **Tool Design & MCP Integration — 18%**: tool interfaces, structured errors,
   least privilege, tool distribution, MCP servers, built-in tools.
5. **Context Management & Reliability — 15%**: long-conversation context,
   escalation/ambiguity, error propagation, human review, provenance.

The three biggest domains (architecture + config + prompting) are ~67% of the
material — weight attention there first.

## Topic map

| File | Covers | Primary domain |
|---|---|---|
| [agent-architecture.md](agent-architecture.md) | Agentic loops, stop_reason (incl. pause_turn/refusal), loop statelessness, tool-use flow, coordinator-subagent, orchestrator-worker economics (~90.2% / ~15×) + multi-vs-single by work shape, subagents/Task/AgentDefinition + Task→Agent rename + no-nesting + exact context boundary, Claude Code subagent config (model-resolution & tool-compose order) + built-in subagents (Explore/Plan/general-purpose) + scope & precedence + design levers + anti-patterns, decomposition (fixed vs adaptive, narrow-decomposition, attention dilution, structural-vs-capability), multi-step orchestration, session state (resume/fork/from-pr, stale-context trap) | Architecture (27%) |
| [workflow-enforcement-and-hooks.md](workflow-enforcement-and-hooks.md) | Hooks (PreToolUse blocks / PostToolUse reshapes, exit codes, fail-open, taxonomy), programmatic guards vs prompts, the enforcement ladder, state machines, structured human handoff | Architecture (27%) |
| [tools-and-mcp.md](tools-and-mcp.md) | Tool interface/description design, selection-reliability debug order, distribution & least privilege + tool profiles (research/reviewer/modifier), structured errors, error recovery/retry, tool_choice, MCP scoping + HTTP transport, community-vs-custom, built-in tools (Edit-anchor order) | Tools & MCP (18%) |
| [prompting-and-structured-output.md](prompting-and-structured-output.md) | Explicit criteria over vague, specificity, classification consistency / false positives, few-shot, input-output examples, structured output via tool-use/JSON schema, tool_choice, validation-retry | Prompting (20%) |
| [claude-code-config.md](claude-code-config.md) | CLAUDE.md hierarchy & precedence (+ CLAUDE.local, concatenation semantics, delivery-as-user-message), modular @import, .claude/rules path globs, the four config surfaces (CLAUDE.md/skills/commands/hooks) + commands↔skills equivalence, skills progressive disclosure / trigger engineering / troubleshooting / invocation control (allowed-tools grants, disable-model-invocation, user-invocable, Skill() rules) / lifecycle & compaction / multi-file structure / dynamic !command injection / skills×subagents wiring, plan mode vs direct, iterative refinement / TDD / interview | Config (20%) |
| [ci-cd-and-review-bots.md](ci-cd-and-review-bots.md) | Headless `-p`, structured JSON output, session isolation, incremental review, test-gen quality, multi-instance review, batch-vs-sync cost decision | Config (20%) + Prompting |
| [context-reliability-and-cost.md](context-reliability-and-cost.md) | Context window, lost-in-the-middle, progressive-summarization risk, tool-output trimming, caching, escalation/ambiguity, error propagation, graceful degradation, provenance, human review/calibration, batch & routing cost | Context & Reliability (15%) |
