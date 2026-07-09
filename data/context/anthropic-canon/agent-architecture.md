# Agent Architecture & Orchestration

Domain 1 (27%). The agentic loop, tool-use mechanics, multi-agent
coordinator-subagent design, task decomposition, and session state.

## Agentic loop lifecycle & control

- The loop: send request → inspect `stop_reason` → if `tool_use`, execute the tool(s), append the assistant message AND tool results to history → re-invoke → repeat until `end_turn` (https://www.anthropiccertifications.com/learn/agentic-architecture/agentic-loop-lifecycle).
- `stop_reason` is the only reliable loop-control signal: continue while `tool_use`, terminate on `end_turn` (https://www.anthropiccertifications.com/learn/agentic-architecture/agentic-loop-lifecycle).
- Anti-patterns: parsing natural-language "I'm done" cues to decide termination; treating presence of assistant text as completion; using an iteration cap as the primary stop mechanism (https://www.anthropiccertifications.com/learn/agentic-architecture/agentic-loop-lifecycle).
- A max-iteration cap is a safety guardrail against runaway loops — a backup, not the control mechanism; iteration count should scale with task complexity (https://www.anthropiccertifications.com/learn/agentic-architecture/agentic-loop-lifecycle).
- `stop_reason` values: `end_turn` (present to user), `max_tokens` (output may be truncated — handle/raise limit), `stop_sequence` (parse up to it), `tool_use` (run tools, return results) (https://www.anthropiccertifications.com/learn/agentic-architecture/agentic-loop-lifecycle).
- Log each iteration for debuggability (https://www.anthropiccertifications.com/learn/agentic-architecture/agentic-loop-lifecycle).

## Tool-use flow & mechanics

- Structured cycle: define tools in the request → Claude returns a `tool_use` block (`id`, `name`, `input`) with `stop_reason: tool_use` → your app executes → you return a `tool_result` block referencing the `tool_use` id → Claude answers or calls more tools. Mnemonic: define → select → execute → return (https://www.anthropiccertifications.com/learn/agentic-architecture/tool-use-flow).
- Parallel tool use: Claude can request several tools in one turn; run them and return all results together before the next call to cut round-trips (https://www.anthropiccertifications.com/learn/agentic-architecture/tool-use-flow).
- Prefer model-driven tool selection (Claude reasons the next tool from context) over hard-coded decision trees — it adapts to novel situations; use pre-configured sequences only where determinism outweighs flexibility (https://www.anthropiccertifications.com/learn/agentic-architecture/tool-use-flow).

## Coordinator-subagent (orchestrator / hub-and-spoke) pattern

- One coordinator owns all routing, error handling, and result aggregation; subagents never talk to each other — everything routes through the hub, giving centralized observability and single-point error handling (https://www.anthropiccertifications.com/learn/agentic-architecture/coordinator-subagent).
- Subagents run with isolated context — they do NOT inherit the coordinator's conversation history; the coordinator decides exactly what each subagent sees (https://www.anthropiccertifications.com/learn/agentic-architecture/coordinator-subagent).
- Dynamic routing: analyze the query and invoke only the subagents needed — a simple query may hit one; do not force everything through the full pipeline (https://www.anthropiccertifications.com/learn/agentic-architecture/coordinator-subagent).
- Iterative refinement: the coordinator inspects synthesis output for gaps, re-delegates targeted queries, and re-runs synthesis until coverage is adequate (https://www.anthropiccertifications.com/learn/agentic-architecture/coordinator-subagent).
- Benefits: centralized visibility, consistent recovery, information control (filter what each agent receives), and swappable downstream agents (https://www.anthropiccertifications.com/learn/agentic-architecture/coordinator-subagent).

## Subagent invocation, Task tool, AgentDefinition

- Subagents are spawned via the `Task` tool; each `Task` call launches one independent run. The coordinator's `allowedTools` MUST include `"Task"` or it cannot delegate at all (https://www.anthropiccertifications.com/learn/agentic-architecture/subagent-invocation).
- Spawn subagents in parallel by emitting multiple `Task` calls in a single coordinator response — not spread across turns (https://www.anthropiccertifications.com/learn/agentic-architecture/subagent-invocation).
- Context isolation is absolute: assume a subagent knows nothing beyond its prompt. Pass complete prior findings explicitly; use structured formats that keep content separate from metadata (URLs, doc names, page numbers) so attribution survives (https://www.anthropiccertifications.com/learn/agentic-architecture/subagent-invocation).
- `AgentDefinition` configures each subagent type via three fields: **description** (coordinator uses it to decide when to invoke), **system prompt** (behavior/constraints), and **tool restrictions** (least privilege) (https://www.anthropiccertifications.com/learn/agentic-architecture/agent-definition-config).
- Write coordinator/subagent prompts as goals + quality criteria, not rigid step-by-step procedures, so the subagent adapts to the specific query (https://www.anthropiccertifications.com/learn/agentic-architecture/agent-definition-config).
- Don't summarize away details a downstream subagent needs — forward both web-search and document-analysis outputs to a synthesis agent intact (https://www.anthropiccertifications.com/learn/agentic-architecture/agent-definition-config).

## Task decomposition: fixed vs adaptive, and narrow-decomposition risk

- Fixed sequential pipeline (prompt chaining): for predictable multi-aspect workflows with known stages and stable inputs/outputs (e.g., extract → validate → transform → load); quality comes from thoroughness (https://www.anthropiccertifications.com/learn/agentic-architecture/task-decomposition-strategies).
- Adaptive decomposition: for open-ended work where scope is unknown until you investigate and early findings reshape next steps (e.g., "add tests to a legacy codebase" — map structure, find high-impact gaps, then adapt); exploration precedes planning (https://www.anthropiccertifications.com/learn/agentic-architecture/task-decomposition-strategies).
- Attention dilution: a large single-pass input (e.g., a 50-file PR in one shot) makes the model miss issues buried in the middle. Fix with two-pass decomposition — per-file local analysis for focused attention, then a cross-file integration pass for interactions (https://www.anthropiccertifications.com/learn/agentic-architecture/task-decomposition-strategies).
- Narrow-decomposition risk: splitting a broad topic too narrowly yields gaps even when every subagent succeeds (e.g., "AI impact on creative industries" split only into visual-arts subtasks silently omits music, writing, film). Root cause is the decomposition scope, not tool or synthesis failure (https://www.anthropiccertifications.com/learn/agentic-architecture/narrow-decomposition-risk).
- Guard against it: require domain enumeration first (list all relevant sub-domains, then make subtasks against that list), add a coverage-validation step after decomposition, and partition assignments by distinct subtopic/source type per agent to cut overlap (https://www.anthropiccertifications.com/learn/agentic-architecture/narrow-decomposition-risk).
- Diagnostic rule: if all subagents succeed but the aggregate is incomplete, suspect the coordinator's decomposition, not execution (https://www.anthropiccertifications.com/learn/agentic-architecture/narrow-decomposition-risk).
- Route by complexity: send each task to the cheapest model meeting the quality bar; use a lightweight model (Haiku) as a classifier that gates escalation to larger models, and monitor per-tier quality to validate routing (https://www.anthropiccertifications.com/learn/agentic-architecture/task-decomposition-routing).

## Multi-step orchestration of multi-concern requests

- A multi-concern request ("charged twice, discount didn't apply, want to cancel") handled sequentially is slow, refetches the same data per concern, and loses context between concerns (https://www.anthropiccertifications.com/learn/agentic-architecture/multi-step-orchestration).
- Fix: decompose into distinct concerns → fetch shared data (e.g., customer record) ONCE and reuse → investigate concerns in parallel → synthesize one unified resolution (https://www.anthropiccertifications.com/learn/agentic-architecture/multi-step-orchestration).
- If single-concern accuracy is high (~94%) but multi-concern degrades (~58%), add few-shot examples showing correct reasoning and tool sequences for multi-concern messages (https://www.anthropiccertifications.com/learn/agentic-architecture/multi-step-orchestration).

## Session state, resumption, forking

- `--resume <session-name>` continues a specific named prior conversation, preserving full history including previous tool results (https://www.anthropiccertifications.com/learn/agentic-architecture/session-state).
- `fork_session` branches from a shared baseline so you can explore divergent approaches independently (e.g., compare two refactor strategies) without losing the original analysis (https://www.anthropiccertifications.com/learn/agentic-architecture/session-state).
- Decision rule: prior context mostly valid → resume; files changed since last session → resume but tell the agent exactly which files changed for targeted re-analysis; prior tool results stale (underlying data changed) → start fresh with an injected structured summary (resuming on stale results makes the agent reason from outdated info); exploring a different approach → fork (https://www.anthropiccertifications.com/learn/agentic-architecture/session-state).
