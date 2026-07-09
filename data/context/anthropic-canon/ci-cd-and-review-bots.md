# CI/CD & Review Bots

Domain 2 (20%) + Prompting (20%). How to embed Claude Code in automated
pipelines for review, test generation, and security analysis — directly
relevant to this repo's `claude-review.yml` review bot and CI gates.

## Headless invocation & structured output

- Run headless in CI with `-p` / `--print`: it consumes the prompt, writes the result to stdout, and exits. Without it, Claude Code blocks waiting for interactive input and the job hangs (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-integration).
- For machine-readable findings, combine `--output-format json` with `--json-schema <schema>` so a pipeline can parse results and post them as inline PR comments; parsing natural language instead is fragile (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-structured-output).
- Structured-output pipeline: invoke with `--output-format json --json-schema` → CI parses the JSON → post findings as inline PR comments anchored to the relevant line → developers get positioned, actionable feedback (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-structured-output).
- To turn narrative CI review output into per-finding inline PR comments, use CLI `--output-format json` + `--json-schema` to enforce structured findings, then parse and post via the GitHub API (beats prompt templates, CLAUDE.md format sections, or a post-hoc summarization step) (https://www.anthropiccertifications.com/learn/prompt-engineering-output/structured-output-json).

## Session isolation — the reviewer must be independent

- Do NOT have the session that wrote the code review its own code: a model that generated code retains its reasoning and is biased against questioning itself. A fresh, independent Claude instance (no prior context) catches subtle issues better than self-review instructions or extended thinking (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-integration).
- Use separate sessions for generation vs review (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-integration).
- For large reviews, split into per-file local passes plus a separate cross-file integration pass to avoid attention dilution and contradictory findings; optionally have the model self-report confidence per finding to route review (https://www.anthropiccertifications.com/learn/prompt-engineering-output).

## Feeding project context to CI-invoked runs

- Provide CI-invoked Claude project context via CLAUDE.md — testing standards, what counts as a valuable test, fixture conventions, available test utilities, review criteria, and severity definitions. This raises output quality and cuts low-value noise (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-integration).

## Incremental review — no duplicate comments

- On re-runs after new commits, put prior findings into the prompt context and instruct Claude to surface only NEW or still-unaddressed issues — duplicate comments erode developer trust (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-structured-output).

## Review-bot precision (ties to prompting canon)

- Give the review bot explicit categorical criteria and per-severity concrete code examples, not vague goals — vague criteria produce false positives that erode trust in all categories (https://www.anthropiccertifications.com/learn/prompt-engineering-output/explicit-criteria).
- If a category is noisy, temporarily disable it, refine its prompt, and re-enable only when precision clears a threshold — keep high-precision categories (security, correctness) running throughout (https://www.anthropiccertifications.com/learn/prompt-engineering-output/classification-consistency).

## Test generation quality

- Supply existing test files so generated tests don't duplicate covered scenarios; document in CLAUDE.md what's worth testing; list available fixtures/utilities so helpers aren't reinvented; define testing standards (naming, Arrange-Act-Assert) (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-structured-output).

## Sync vs batch — the cost/latency decision

- Workflow selection: pre-merge review → synchronous with `-p`, needs low latency, use a session separate from the author; test generation → `-p` with existing tests in context; security audit → scheduled, can use the batch API (tolerates latency, ~50% cheaper) (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-structured-output).
- Decision rule: use the batch API only for latency-tolerant work — overnight/technical-debt/security reports are good candidates; a blocking pre-merge check that gates merges must stay synchronous, never batched (https://www.anthropiccertifications.com/learn/claude-code-workflows/ci-cd-integration).
