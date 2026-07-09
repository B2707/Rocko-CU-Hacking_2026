# Context Management, Reliability & Cost

Domain 5 (15%) plus cost levers. Keeping long conversations coherent, degrading
gracefully, preserving provenance, calibrating human review, and controlling spend.

## Context window fundamentals

- The context window = input tokens + output tokens combined; always pass complete conversation history in follow-up requests to keep coherence (https://www.anthropiccertifications.com/learn/context-management).
- "Lost in the middle": models attend reliably to the start and end of long inputs and may drop findings buried in the middle. Mitigation — put a key-findings summary at the TOP of aggregated inputs and use explicit section headers for the details (https://www.anthropiccertifications.com/learn/context-management).

## Progressive-summarization risk & persistent case facts

- Summarizing compresses hard facts (amounts, dates, order numbers, statuses, customer-stated expectations) into vague prose. Fix — extract transactional "case facts" into a persistent structured block that is re-injected in every prompt, separate from the summarized history (https://www.anthropiccertifications.com/learn/context-management).
- Tool outputs bloat context (40+ fields returned when 5 matter). Trim verbose tool results to only relevant fields before they accumulate; leverage caching for stable content (https://www.anthropiccertifications.com/learn/context-management).

## Escalation & ambiguity

- Escalate to a human on: explicit request for a human (honor immediately, before investigating); genuine policy gaps/ambiguity (not merely "complex"); inability to make meaningful progress. Sentiment and self-reported confidence are unreliable complexity proxies (https://www.anthropiccertifications.com/learn/context-management).
- Ambiguity: when a tool returns multiple matches (e.g., several customer records), ask for an additional identifier rather than guessing via heuristics; encode escalation/ambiguity rules as explicit system-prompt criteria with few-shot examples (https://www.anthropiccertifications.com/learn/context-management).

## Error propagation in multi-agent systems

- Handle each error at the lowest level able to resolve it: subagents locally retry transient failures and only propagate what they can't fix, returning structured error context — failure type, what was attempted, partial results, and alternative approaches — so the coordinator can recover intelligently (https://www.anthropiccertifications.com/learn/context-management).
- Distinguish access failures (timeouts needing retry) from valid empty results (successful query, no matches) (https://www.anthropiccertifications.com/learn/context-management).
- Anti-patterns: generic statuses like "search unavailable" that hide context; silently returning empty-as-success; killing the whole workflow on one failure (https://www.anthropiccertifications.com/learn/context-management).

## Graceful degradation with transparency

- Keep operating on partial data but annotate coverage — which findings are well-supported vs which topic areas have gaps from unavailable sources (https://www.anthropiccertifications.com/learn/context-management).

## Large-codebase exploration

- Extended sessions degrade — the model starts citing "typical patterns" instead of specific classes it found earlier. Counter with: scratchpad files that externalize key findings across context boundaries; subagent delegation to isolate verbose exploration while the main agent holds high-level coordination; summarizing a phase before spawning the next phase's subagents; and `/compact` to reclaim context (https://www.anthropiccertifications.com/learn/context-management).
- Design crash recovery via structured per-agent state exports — a manifest the coordinator reloads and injects on resume (https://www.anthropiccertifications.com/learn/context-management).

## Human review & confidence calibration

- Aggregate accuracy (e.g., 97%) can hide poor performance on specific document types or fields — validate accuracy per document type and per field before automating (https://www.anthropiccertifications.com/learn/context-management).
- Use stratified random sampling of high-confidence extractions to measure ongoing error rates and catch novel error patterns; have the model emit field-level confidence; calibrate thresholds against a labeled validation set (not intuition); route low-confidence or contradictory-source cases to humans (https://www.anthropiccertifications.com/learn/context-management).

## Information provenance in multi-source synthesis

- Attribution is lost when summarization compresses findings without keeping claim→source mappings. Require subagents to output structured claim-source mappings (URLs, doc names, excerpts) that survive synthesis (https://www.anthropiccertifications.com/learn/context-management).
- For conflicting statistics from credible sources, preserve all values with source attribution and annotate the conflict rather than silently picking one; let the coordinator reconcile. Require publication/collection dates in structured output so temporal differences aren't misread as contradictions (https://www.anthropiccertifications.com/learn/context-management).
- Render content types natively in synthesis (financial data as tables, news as prose, technical findings as lists) instead of flattening everything (https://www.anthropiccertifications.com/learn/context-management).

## Cost levers

- Route by complexity: send each task to the cheapest model meeting the quality bar; use a lightweight model (Haiku) as a classifier that gates escalation to larger models; monitor per-tier quality to validate routing (https://www.anthropiccertifications.com/learn/agentic-architecture/task-decomposition-routing).
- Batch API: ~50% cheaper, up to a 24-hour window, no latency SLA — use for latency-tolerant scheduled work (overnight reports, nightly test gen, security audits); keep merge-gating checks synchronous (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-integration).
- Caching: leverage prompt caching for stable content (e.g., a stable system prompt, re-injected case-facts block) so repeated tokens aren't re-billed; keep cached content stable by encoding few-shot examples as `messages` turns rather than mutating the system prompt (https://www.anthropiccertifications.com/learn/context-management).
- Trim tool outputs and load context via progressive disclosure (skills/rules loaded only when relevant) to cut token spend (https://www.anthropiccertifications.com/learn/claude-code-workflows/modular-organization).
