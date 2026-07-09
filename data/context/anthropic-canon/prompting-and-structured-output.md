# Prompt Engineering & Structured Output

Domain 3 (20%). Explicit criteria over vague instructions, few-shot, guaranteed
structured output, and validation-retry.

## Explicit criteria beat vague instructions

- Vague directives ("check comments are accurate", "be conservative", "only high-confidence findings") give the model no calibrated threshold and produce both false positives and false negatives; confidence-based hedging does NOT raise precision (https://www.anthropiccertifications.com/learn/prompt-engineering-output/explicit-criteria).
- Convert goals into categorical criteria: e.g., "flag a comment only when its claimed behavior contradicts the actual code behavior" (https://www.anthropiccertifications.com/learn/prompt-engineering-output/explicit-criteria).
- Define what should NOT be flagged (acceptable patterns, minor style, local conventions), not just what should; specify which issue classes to report vs skip; attach a concrete code example to each severity level (https://www.anthropiccertifications.com/learn/prompt-engineering-output/explicit-criteria).
- Four specificity principles: define criteria not goals; specify boundaries (what should and should NOT be flagged); use severity definitions with concrete per-level code examples; test criteria against edge cases (https://www.anthropiccertifications.com/learn/prompt-engineering-output/prompt-specificity).
- The system prompt is set via the API `system` parameter, processed before the user turn, and shapes every subsequent response — so imprecision there compounds across the whole conversation (https://www.anthropiccertifications.com/learn/prompt-engineering-output/explicit-criteria).

## Classification consistency & false-positive trust erosion

- One noisy category undermines confidence in ALL categories; false positives erode trust (https://www.anthropiccertifications.com/learn/prompt-engineering-output/classification-consistency).
- Root causes of inconsistent classification: ambiguous category definitions, no concrete per-category examples, and relative rather than absolute criteria (https://www.anthropiccertifications.com/learn/prompt-engineering-output/classification-consistency).
- Fix: give each level a clear definition plus concrete code/content examples, and judge each item on absolute criteria — never "rate severity relative to other issues in this PR/batch" (that causes cross-batch inconsistency) (https://www.anthropiccertifications.com/learn/prompt-engineering-output/classification-consistency).
- False-positive playbook: temporarily disable high-false-positive categories (e.g., style ~52%, docs ~48%), keep high-precision ones running (security ~8%, correctness ~8%), improve the disabled prompts, and re-enable only once precision clears a threshold (https://www.anthropiccertifications.com/learn/prompt-engineering-output/classification-consistency).
- Anti-patterns: relative-to-PR rating; self-reported confidence scores (developers who lost trust won't trust them, and it doesn't fix the root cause); uniform strictness reduction (needlessly harms high-precision categories) (https://www.anthropiccertifications.com/learn/prompt-engineering-output/classification-consistency).

## Few-shot examples & concrete input-output pairs

- Few-shot (concrete input→output example pairs) steers Claude more reliably than instructions alone; reach for it when prose yields inconsistent results, formats must be exact, classification is nuanced, or extraction risks hallucination (https://www.anthropiccertifications.com/learn/prompt-engineering-output/few-shot-prompting).
- Aim examples at the hard/ambiguous cases the model actually fumbles (not obvious ones); show the reasoning (why the output is correct) so the model generalizes judgment instead of pattern-matching; use ~2-4 focused examples (quality beats quantity); diversify scenarios (https://www.anthropiccertifications.com/learn/prompt-engineering-output/few-shot-prompting).
- Idiomatic few-shot on the Claude API encodes examples as alternating `user`/`assistant` turns in the `messages` array (mirrors training format) rather than stuffing them into the system prompt — this also keeps cached system-prompt content stable for prompt caching (https://www.anthropiccertifications.com/learn/prompt-engineering-output/few-shot-prompting).
- When prose fails to pin down exact requirements, show 2-3 representative input→output pairs of the exact transformation (snake_case→camelCase, ISO timestamp→human date, flattening nested objects); "show, don't tell" (https://www.anthropiccertifications.com/learn/prompt-engineering-output/input-output-examples).
- Make examples demonstrate the full desired output shape (for code review: file, line, severity, suggested fix, reasoning); include examples with empty/null values for absent fields so the model learns not to fabricate (https://www.anthropiccertifications.com/learn/prompt-engineering-output/input-output-examples).
- Decision rule: after two prose iterations still miss the target structure, 2-3 concrete input-output examples beat more-precise prose, writing a schema, or asking Claude to explain its interpretation (https://www.anthropiccertifications.com/learn/prompt-engineering-output/input-output-examples).

## Guaranteed structured output

- Reliability ladder (least → most): prompt-based formatting (unreliable) → few-shot of the exact format (good for interactive) → CLI `--output-format json --json-schema` (guaranteed for CLI runs) → API tool use with a JSON Schema (most reliable) (https://www.anthropiccertifications.com/learn/prompt-engineering-output/structured-output-json).
- Why tool use wins: the model must return data matching the schema, so JSON *syntax* errors are eliminated and `tool_use` blocks are always valid JSON — but it does NOT prevent *semantic* errors (line items not summing to the total, values in the wrong field) (https://www.anthropiccertifications.com/learn/prompt-engineering-output/structured-output-json).
- Schema-design: make fields optional/nullable when the source may lack them (prevents fabrication to satisfy `required`); use enum values like `"unclear"` for ambiguity; use an `"other"` + free-text detail pattern for extensible categories; pair strict schemas with normalization rules in the prompt (https://www.anthropiccertifications.com/learn/prompt-engineering-output/structured-output-json).
- Extract structured data from the `tool_use` content block, not from text output (https://www.anthropiccertifications.com/learn/prompt-engineering-output/structured-output-config).
- `tool_choice` for structured output: `"any"` when several extraction schemas exist and the input type is unknown; force a specific tool to guarantee one extraction runs as a pipeline step before enrichment (https://www.anthropiccertifications.com/learn/prompt-engineering-output/structured-output-config).

## Validation & retry with error feedback

- On invalid output, retry with the *specific* validation errors — not a bare "try again": send a follow-up containing the original source document, the failed output, and the exact validation errors so the model self-corrects (https://www.anthropiccertifications.com/learn/prompt-engineering-output/validation-retry).
- Retries work for format mismatches, structural errors, and semantic errors (the model can reformat/restructure/recalculate); they FAIL when the information is simply absent from the source (the model will fabricate) or lives in an external doc not provided (https://www.anthropiccertifications.com/learn/prompt-engineering-output/validation-retry).
- Self-correcting validation flows: extract `calculated_total` alongside `stated_total` to flag mismatches; add a `conflict_detected` boolean for inconsistent source data; these computed fields enable automated validation without human review (https://www.anthropiccertifications.com/learn/prompt-engineering-output/validation-retry).

## Batch API for latency-tolerant prompting

- The Message Batches API is ~50% cheaper with up to a 24-hour window and no latency SLA; use it for non-blocking work (overnight reports, nightly test generation) and the synchronous API for blocking pre-merge checks (https://www.anthropiccertifications.com/learn/prompt-engineering-output). 
- Batch does NOT support multi-turn tool calling within one request; correlate request/response pairs via `custom_id`; on failure resubmit only the failed `custom_id`s (not the whole batch); refine prompts on a small sample first since resubmissions eat into the 50% saving (https://www.anthropiccertifications.com/learn/prompt-engineering-output).
