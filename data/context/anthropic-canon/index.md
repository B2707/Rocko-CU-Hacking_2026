# Anthropic Agentic-Workflows Canon

The team's grounded evidence base for how agentic workflows, harness config,
tools/MCP, prompting, review bots, and context/cost are *supposed* to be built.
Every claim here is distilled in our own words from Anthropic's Claude Certified
Architect (CCA-F) concept library; no verbatim course prose is reproduced. Each
bullet ends with the source page URL in parens so a finding can be traced back.

- **Source site:** https://www.anthropiccertifications.com/learn
- **Distilled:** 2026-07-08
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
| [agent-architecture.md](agent-architecture.md) | Agentic loops, stop_reason, tool-use flow, coordinator-subagent, subagents/Task/AgentDefinition, decomposition (fixed vs adaptive, narrow-decomposition, attention dilution), multi-step orchestration, session state | Architecture (27%) |
| [workflow-enforcement-and-hooks.md](workflow-enforcement-and-hooks.md) | Hooks (PostToolUse + call interception), programmatic guards vs prompts, the enforcement ladder, state machines, structured human handoff | Architecture (27%) |
| [tools-and-mcp.md](tools-and-mcp.md) | Tool interface/description design, selection-reliability debug order, distribution & least privilege, structured errors, error recovery/retry, tool_choice, MCP scoping, community-vs-custom, built-in tools | Tools & MCP (18%) |
| [prompting-and-structured-output.md](prompting-and-structured-output.md) | Explicit criteria over vague, specificity, classification consistency / false positives, few-shot, input-output examples, structured output via tool-use/JSON schema, tool_choice, validation-retry | Prompting (20%) |
| [claude-code-config.md](claude-code-config.md) | CLAUDE.md hierarchy & precedence, modular @import, .claude/rules path globs, the four config surfaces (CLAUDE.md/skills/commands/hooks), plan mode vs direct, iterative refinement / TDD / interview | Config (20%) |
| [ci-cd-and-review-bots.md](ci-cd-and-review-bots.md) | Headless `-p`, structured JSON output, session isolation, incremental review, test-gen quality, multi-instance review, batch-vs-sync cost decision | Config (20%) + Prompting |
| [context-reliability-and-cost.md](context-reliability-and-cost.md) | Context window, lost-in-the-middle, progressive-summarization risk, tool-output trimming, caching, escalation/ambiguity, error propagation, graceful degradation, provenance, human review/calibration, batch & routing cost | Context & Reliability (15%) |
