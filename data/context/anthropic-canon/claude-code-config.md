# Claude Code Configuration & Workflows

Domain 2 (20%). CLAUDE.md hierarchy, the four config surfaces, path-specific
rules, plan mode, and iterative refinement.

## CLAUDE.md hierarchy & precedence

- Sources and precedence: project `CLAUDE.md` (root or `.claude/CLAUDE.md`, loaded every conversation) → directory-level `CLAUDE.md` (additive, only when working in that directory) → user-level `~/.claude/CLAUDE.md` (personal, lowest priority, NOT version-controlled). `.claude/rules/` files load conditionally (https://www.anthropiccertifications.com/learn/claude-code-workflows/claude-md-hierarchy).
- Project scope overrides user scope for same-named skills/configs; CLAUDE.md is re-read fresh each session (no cross-session caching) (https://www.anthropiccertifications.com/learn/claude-code-workflows/claude-md-hierarchy).
- Common failure / decision rule: shared guidelines stashed only in each dev's `~/.claude/CLAUDE.md` never reach new teammates — move shared guidance into project scope (`.claude/CLAUDE.md` or root) so it is version-controlled (https://www.anthropiccertifications.com/learn/claude-code-workflows/claude-md-hierarchy).
- Use `/memory` to verify which memory files are loaded and to debug behavior that varies across sessions (https://www.anthropiccertifications.com/learn/claude-code-workflows/claude-md-hierarchy).
- Restructuring rule: for a bloated (400+ line) CLAUDE.md, keep universal always-apply standards (coding, testing) in CLAUDE.md and move task-specific workflows (PR review, deploys, migrations) into Skills that load on demand (https://www.anthropiccertifications.com/learn/claude-code-workflows/claude-md-hierarchy).

## Modular organization: @import and .claude/rules/

- `@import` references external standards files (e.g., `@import ./standards/testing.md`) so each package's CLAUDE.md pulls in only the standards relevant to its domain (https://www.anthropiccertifications.com/learn/claude-code-workflows/modular-organization).
- `.claude/rules/` splits a large CLAUDE.md into focused topic files (`testing.md`, `api-conventions.md`, `deployment.md`) (https://www.anthropiccertifications.com/learn/claude-code-workflows/modular-organization).
- When to use each: single CLAUDE.md → small projects; `@import` → monorepos where packages share *some* standards; `.claude/rules/` → large projects needing topic-specific, conditionally-loaded rules. The benefit is less context bloat — Claude loads only what's relevant, cutting irrelevant tokens (https://www.anthropiccertifications.com/learn/claude-code-workflows/modular-organization).

## Path-specific rules

- `.claude/rules/` files can carry YAML frontmatter with a `paths` field of glob patterns (e.g., `paths: ["**/*.test.tsx", "**/*.spec.ts"]`); the rule loads only when the edited file matches a glob, cutting irrelevant context and tokens (https://www.anthropiccertifications.com/learn/claude-code-workflows/path-specific-rules).
- Which config to reach for: directory-level CLAUDE.md → conventions confined to one directory subtree; path-specific rules (globs) → conventions tied to a file *type* scattered across many directories (e.g., test-file standards); root CLAUDE.md → universal conventions (https://www.anthropiccertifications.com/learn/claude-code-workflows/path-specific-rules).
- Prefer glob-pattern rules over a subdirectory CLAUDE.md when a convention spans files scattered across directories — globs match by file type regardless of location (https://www.anthropiccertifications.com/learn/claude-code-workflows/path-specific-rules).

## The four config surfaces (distinguished by WHEN each loads)

- `CLAUDE.md` → loaded every conversation, always → universal standards/context (https://www.anthropiccertifications.com/learn/claude-code-workflows/custom-skills-commands).
- Skills (`SKILL.md`) → on-demand when the description matches a task → task-specific workflows Claude auto-invokes (https://www.anthropiccertifications.com/learn/claude-code-workflows/custom-skills-commands).
- Slash commands → on-demand when you type `/name` → workflows you trigger explicitly (https://www.anthropiccertifications.com/learn/claude-code-workflows/custom-skills-commands).
- Hooks → automatically on a lifecycle event (e.g., PostToolUse) → deterministic actions the harness runs, not decided by Claude (https://www.anthropiccertifications.com/learn/claude-code-workflows/custom-skills-commands).
- Mental model: CLAUDE.md is always-on context; skills/commands are progressive disclosure (pulled in only when relevant, keeping base context small); hooks are harness-executed. Decision rule: CLAUDE.md = always-loaded universal standards; skills = on-demand task-specific workflows; anything that must run automatically on every tool use is a hook, not a skill (https://www.anthropiccertifications.com/learn/claude-code-workflows/custom-skills-commands).

## Skills & slash commands: scope and frontmatter

- Scope & precedence: `.claude/skills/` and `.claude/commands/` are project-scoped (shared via VCS); `~/.claude/skills/` and `~/.claude/commands/` are personal. A same-named project skill wins over a personal one — give personal variants distinct names (e.g., `/review-fast`) to avoid shadowing (https://www.anthropiccertifications.com/learn/claude-code-workflows/custom-skills-commands).
- SKILL.md frontmatter keys: `description` (natural-language trigger — write it to name the task and the activation cues; matching depends on this); `allowed-tools` (whitelist enforcing least privilege, e.g., `Read`, `Edit`, `mcp__github__*` — omitting it can over-grant); `context` (`fork` = isolated sub-agent context discarded on completion, `current` = inline in the main conversation); `argument-hint` (surfaces expected params in autocomplete); `model` (can pin a model, e.g., `haiku`) (https://www.anthropiccertifications.com/learn/claude-code-workflows/skill-frontmatter-config).
- When to `context: fork`: for exploratory/verbose work (codebase scans, brainstorming, research) so intermediate output doesn't pollute the main conversation and abandoned approaches don't bias later implementation — only the conclusion returns. Run `current` when the skill needs the surrounding conversation or you want its step-by-step output visible (https://www.anthropiccertifications.com/learn/claude-code-workflows/skill-frontmatter-config).
- Common mistakes: vague `description` (skill won't trigger); missing `allowed-tools` (over-privileged); wrong scope or same-name shadowing; using a skill where a hook belongs (https://www.anthropiccertifications.com/learn/claude-code-workflows/custom-skills-commands).
- Exam decision rule: a skill whose comprehensive analysis makes Claude lose track of the task → add `context: fork` to isolate it (rather than compressing output, swapping models, or splitting the skill) (https://www.anthropiccertifications.com/learn/claude-code-workflows/skill-frontmatter-config).

## Plan mode vs direct execution

- Plan mode (explore/analyze without writing files or running commands) when: requirements are ambiguous or multiple valid approaches exist; large-scope architectural change (monolith→microservices, a migration touching many files); choosing among integration approaches with different infra implications (https://www.anthropiccertifications.com/learn/claude-code-workflows/plan-mode-vs-direct).
- Direct execution when: the task is well-defined with clear scope (single-file bug fix with a clear stack trace, add one conditional, routine generation following established conventions) (https://www.anthropiccertifications.com/learn/claude-code-workflows/plan-mode-vs-direct).
- Best combined workflow: plan mode to investigate and weigh approaches, then switch to direct execution to build the chosen one (https://www.anthropiccertifications.com/learn/claude-code-workflows/plan-mode-vs-direct).
- Explore subagent: for a verbose discovery phase (e.g., locating all API calls across 120 files), delegate to the Explore subagent so it isolates the noisy output and returns only a summary — preserving the main context window (https://www.anthropiccertifications.com/learn/claude-code-workflows/plan-mode-vs-direct).
- Decision rule: when a ticket names a feature but not the integration method and the methods differ architecturally (Slack via webhooks vs bot tokens vs Apps), enter plan mode to explore and present a recommendation before implementing (https://www.anthropiccertifications.com/learn/claude-code-workflows/plan-mode-vs-direct).

## Iterative refinement

- Concrete input/output examples: when prose is interpreted inconsistently, give 2-3 literal input→expected-output pairs — removes ambiguity far better than "format dates in a human-readable way" (https://www.anthropiccertifications.com/learn/claude-code-workflows/iterative-refinement).
- Test-driven iteration: write test suites (behavior, edge cases, performance) before implementation; run tests and share the *failures* with Claude so each iteration targets specific failing tests. More effective than manual review because failures are unambiguous and progress is measurable (X of Y passing) (https://www.anthropiccertifications.com/learn/claude-code-workflows/test-driven-iteration).
- Interview pattern: in unfamiliar domains, have Claude ask clarifying questions first (cache invalidation, partial-failure handling, concurrency) — front-loads design decisions and yields better first passes (https://www.anthropiccertifications.com/learn/claude-code-workflows/test-driven-iteration).
- Batched vs sequential feedback: interacting problems → one detailed message with all issues (fixes affect each other, Claude needs the full picture); independent problems → fix one at a time (https://www.anthropiccertifications.com/learn/claude-code-workflows/iterative-refinement).
- Edge cases: give a specific input/expected-output test case rather than an abstract prose description, which produces incomplete fixes (https://www.anthropiccertifications.com/learn/claude-code-workflows/iterative-refinement).
