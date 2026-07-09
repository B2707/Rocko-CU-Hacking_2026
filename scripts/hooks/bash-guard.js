#!/usr/bin/env node
// PreToolUse[Bash] guard — belt-and-suspenders for rules GitHub already
// enforces server-side (protect-main ruleset). Fail-open by design: a broken
// hook must never brick a seat; the ruleset remains the real law.
//
// ./scripts/task internals need no allowlist: this hook sees only the agent's
// command string, and the script's own `gh issue create` runs as a subprocess
// the hook never observes.
'use strict';

const { execSync } = require('child_process');

const ISSUE_CREATE_RE = /\bgh\s+issue\s+create\b/;
const GIT_PUSH_RE = /\bgit\s+push\b/;
// Explicit main refspec on any remote except `event` (Day-0 instantiation door).
const PUSH_MAIN_RE = /\bgit\s+push\b(?:\s+(?:-\S+|--\S+))*\s+(?!event\b)\S+\s+(?:\+?main\b|HEAD:main\b)/;
const HAS_REFSPEC_RE = /\bgit\s+push\b(?:\s+(?:-\S+|--\S+))*\s+\S+\s+\S+/;
const GIT_TIMEOUT_MS = 5000;

function deny(reason) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: reason,
    },
  }));
  process.exit(0);
}

function currentBranch(cwd) {
  try {
    return execSync('git rev-parse --abbrev-ref HEAD', {
      cwd, timeout: GIT_TIMEOUT_MS, stdio: ['ignore', 'pipe', 'ignore'],
    }).toString().trim();
  } catch {
    return '';
  }
}

function main(input) {
  const command = String((input.tool_input || {}).command || '');

  if (ISSUE_CREATE_RE.test(command)) {
    deny('Direct `gh issue create` is reserved for the task script (rule K1). '
      + 'Use: ./scripts/task propose "<title>" — it labels and routes correctly.');
  }

  if (GIT_PUSH_RE.test(command)) {
    if (PUSH_MAIN_RE.test(command)) {
      deny('Pushes to main are blocked (the GitHub ruleset rejects them anyway). '
        + 'Ship via PR: ./scripts/task ship. Day-0 instantiation '
        + '(`git push event main`) is exempt; everything else goes through a task/* branch.');
    }
    if (!HAS_REFSPEC_RE.test(command) && currentBranch(input.cwd) === 'main') {
      deny('You are on main — a bare `git push` would target main. '
        + 'Start a task branch first: ./scripts/task start <issue#>.');
    }
  }

  process.exit(0);
}

let raw = '';
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('end', () => {
  try { main(JSON.parse(raw)); }
  catch (err) {
    // Fail open (never brick a seat), but record WHY — a silent exit here
    // would hide a disabled gate. Lazy-require so a broken logger can't
    // disable this gate's main path.
    try { require('./hook-log').logHookError('bash-guard', err); } catch { /* best-effort */ }
    process.exit(0);
  }
});
