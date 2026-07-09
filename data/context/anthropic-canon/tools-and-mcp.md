# Tool Design & MCP Integration

Domain 4 (18%). Tool interfaces, selection reliability, least-privilege
distribution, structured errors, and MCP server config.

## Tool interface & description design

- Tool descriptions are the #1 lever for selection accuracy — the model selects primarily from descriptions; minimal descriptions cause unreliable selection among similar tools (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-interface-design).
- Anatomy of a good tool definition: action-oriented specific name (`lookup_order`, not `data_fetch`); a description saying what it does, when to use it, and when NOT to; JSON-Schema input with per-parameter descriptions; accepted input-format examples; and explicit boundaries vs similar tools (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-interface-design).
- Common mistakes: vague descriptions ("Retrieves customer information"); overlapping names (`analyze_content` vs `analyze_document`); missing "use X instead" boundaries (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-interface-design).
- Split overly generic tools into purpose-specific ones with clear I/O contracts — e.g., `analyze_document` → `extract_data_points`, `summarize_content`, `verify_claim_against_source`; narrower tools = less selection ambiguity (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-interface-design).

## Tool-selection reliability & debugging order

- When the agent keeps picking the wrong tool, debug in a fixed order, not by guessing: (1) inspect tool descriptions first — clear and mutually distinct?; (2) inspect the system prompt for keyword-triggered instructions that hijack routing; (3) add few-shot examples for the ambiguous cases, each showing the reasoning for the choice; (4) for must-happen sequences, enforce ordering in code (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-selection-reliability).
- System-prompt keyword bias: a phrase like "when the user mentions 'account'…" can silently override a good description. Telltale: a tool fires ~78% of the time when a keyword is present vs ~7% when absent — that gap points to a keyword-sensitive prompt, not a description problem (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-selection-reliability).
- Use ~4-6 few-shot examples covering the specific ambiguous scenarios, including why the chosen tool beat the plausible alternative (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-selection-reliability).

## Distribution & least privilege

- Give each agent only the tools its role needs — aim for ~4-5, not ~18; more tools means more decision complexity and worse selection reliability (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-distribution).
- Over-permissioning failure mode: a document-analysis agent handed a general `fetch_url` drifts into ad-hoc web searches (another agent's job), reaches unauthorized resources, and produces role-mixing output (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-distribution).
- Scoping strategies: rename general tools to purpose-specific ones to kill semantic overlap (`fetch_url` → `load_document` that validates the URL is a document; `analyze_content` → `extract_web_results`); validate/constrain inputs; scope by capability; allow narrow cross-role tools (give a synthesis agent a `verify_fact` for simple lookups) while routing complex queries through the coordinator (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-distribution).

## Structured error responses & recovery

- Generic "Operation failed" is harmful: it blocks the agent from deciding whether to retry, what to tell the user, and whether to escalate vs try an alternative (https://www.anthropiccertifications.com/learn/tool-design-mcp/error-response-design).
- The MCP `isError` flag signals a tool failure and crucially distinguishes a real error from a successful-but-empty result (https://www.anthropiccertifications.com/learn/tool-design-mcp/error-response-design).
- Error taxonomy → retryable? → action: Transient (timeout/unavailable) → yes → retry with backoff; Validation (bad input) → no → fix input, retry; Business (policy/limit) → no → inform user, suggest alternative; Permission (unauthorized) → no → escalate or request credentials (https://www.anthropiccertifications.com/learn/tool-design-mcp/error-response-design).
- Recommended structured error fields: `isError`, `errorCategory`, `isRetryable`, a `message` for logs/agent, and a `userFriendlyMessage` to relay to the human (https://www.anthropiccertifications.com/learn/tool-design-mcp/error-response-design).
- Critical distinction: an access failure (DB timeout) needs a retry; a query that succeeded with 0 matches is a valid empty result to accept — confusing them causes either missed data or wasted retries (https://www.anthropiccertifications.com/learn/tool-design-mcp/error-recovery-patterns).
- Match strategy to error type: timeout/unavailable → exponential backoff; rate limit → wait for the reset window; invalid input → fix params; policy/business → inform/escalate/alternative; permission denied → escalate/request creds; file corruption → report, don't retry (https://www.anthropiccertifications.com/learn/tool-design-mcp/error-recovery-patterns).
- Local vs propagated recovery: subagents first retry transient failures (2-3 backoff attempts), try fallback sources, and proceed with annotated partial results; propagate to the coordinator only when local recovery is exhausted, always including what was attempted + partial results + the unresolved failure (https://www.anthropiccertifications.com/learn/tool-design-mcp/error-recovery-patterns).

## tool_choice

- `"auto"` (default): model may reply with text instead of calling a tool — use when a tool may or may not help; risk = plain text when you needed structured data (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-distribution).
- `"any"`: model must call some tool but picks which — use with multiple extraction schemas / unknown input type (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-distribution).
- `{"type":"tool","name":"…"}`: force one specific tool — use to guarantee a prerequisite step runs first (e.g., `extract_metadata` before enrichment), then let Claude choose freely afterward (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-distribution).
- `"none"`: Claude cannot use tools (https://www.anthropiccertifications.com/learn/tool-design-mcp/tool-distribution).

## MCP server config & scoping

- Scoping: project-level `.mcp.json` for shared, version-controlled team tooling; user-level `~/.claude.json` (`claude mcp add --scope user`) for personal/experimental servers (https://www.anthropiccertifications.com/learn/tool-design-mcp/mcp-server-integration).
- Project `.mcp.json` uses an `mcpServers` map; each server has `command`, `args`, and an `env` block. Use env-var expansion like `${GITHUB_TOKEN}` in `env` to keep secrets out of version control while sharing one config; never commit secrets (https://www.anthropiccertifications.com/learn/tool-design-mcp/mcp-server-integration).
- Tools from all configured servers are discovered at connection time and available simultaneously (https://www.anthropiccertifications.com/learn/tool-design-mcp/mcp-server-integration).
- Expose content catalogs (issue summaries, doc hierarchies, DB schemas) as MCP resources so agents see available data without exploratory tool calls (https://www.anthropiccertifications.com/learn/tool-design-mcp/mcp-server-integration).
- Community vs custom: prefer an existing community server for standard integrations (GitHub, Jira, Slack, databases) when it covers your core use cases — you get maintained code without the maintenance burden; build custom only for genuinely team-specific workflows, internal/proprietary APIs, needed fine-grained control, or when community servers fail your security bar (https://www.anthropiccertifications.com/learn/tool-design-mcp/mcp-community-vs-custom).
- Write rich MCP tool descriptions (what it does, output format, when it beats a built-in, which data it touches) — vague ones make the agent fall back to built-in tools like Grep instead of the more capable MCP tool (https://www.anthropiccertifications.com/learn/tool-design-mcp/mcp-community-vs-custom).

## Built-in Claude Code tools

- Grep = search file *contents* (function names, error strings, imports); Glob = match file *paths* by name/pattern (`**/*.test.tsx`, config files). Don't conflate them (https://www.anthropiccertifications.com/learn/tool-design-mcp/builtin-tools).
- Read = load a whole file; Write = create a new file; Edit = targeted change via unique anchor-text match; Bash = run commands (deps, tests, git) (https://www.anthropiccertifications.com/learn/tool-design-mcp/builtin-tools).
- When Edit's anchor text isn't unique (Edit fails), fall back to Read + Write (more reliable but rewrites the whole file) (https://www.anthropiccertifications.com/learn/tool-design-mcp/builtin-tools).
- Build codebase understanding incrementally: Grep for entry points → Read to follow imports/trace flows → Grep again for related code — not by reading everything upfront. To trace usage across wrapper/re-export modules, enumerate the wrapper's exported names, then search each across the codebase (https://www.anthropiccertifications.com/learn/tool-design-mcp/builtin-tools).
