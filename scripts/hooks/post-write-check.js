#!/usr/bin/env node
// PostToolUse[Edit|Write] check — eslint per-file only, and only once an
// eslint config exists at the repo root (a no-op until the stack is stamped).
// Type-checking is deliberately NOT run here: a whole-project `tsc --noEmit`
// on every edit is too slow for per-file feedback, and a file-scoped tsc can't
// resolve project types reliably — so types are enforced by the required CI
// build-test check instead. Failures feed back to the agent (exit 2); missing
// tools and timeouts fail open.
'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const LINT_EXTS = new Set(['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']);
const ESLINT_CONFIGS = [
  'eslint.config.js', 'eslint.config.mjs', 'eslint.config.cjs',
  '.eslintrc', '.eslintrc.js', '.eslintrc.cjs', '.eslintrc.json',
];
const MAX_OUTPUT_LINES = 40;
const CHECK_TIMEOUT_MS = 45000;

// execFileSync with an argument array — no shell, so file paths can't inject.
function run(bin, args, cwd) {
  try {
    execFileSync(bin, args, { cwd, timeout: CHECK_TIMEOUT_MS, stdio: ['ignore', 'pipe', 'pipe'] });
    return null;
  } catch (error) {
    if (error.killed) return null; // timeout — fail open rather than spam the agent
    const out = `${error.stdout || ''}${error.stderr || ''}`.trim();
    return out.split('\n').slice(0, MAX_OUTPUT_LINES).join('\n') || `${bin} ${args.join(' ')} failed`;
  }
}

function main(input) {
  const filePath = String((input.tool_input || {}).file_path || '');
  const projectDir = process.env.CLAUDE_PROJECT_DIR || input.cwd || '';
  if (!filePath || !projectDir || !filePath.startsWith(projectDir)) process.exit(0);

  const ext = path.extname(filePath).toLowerCase();
  const failures = [];

  // No tsc here on purpose — types are covered by the required CI build-test
  // check; this hook stays fast with per-file eslint only (see header note).
  const hasEslint = ESLINT_CONFIGS.some((name) => fs.existsSync(path.join(projectDir, name)));
  if (hasEslint && LINT_EXTS.has(ext)) {
    const result = run('npx', ['--no-install', 'eslint', filePath], projectDir);
    if (result) failures.push(`eslint failed:\n${result}`);
  }

  if (failures.length > 0) {
    process.stderr.write(failures.join('\n\n'));
    process.exit(2); // exit 2 routes this straight back to the agent to fix now
  }
  process.exit(0);
}

let raw = '';
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('end', () => {
  try { main(JSON.parse(raw)); } catch { process.exit(0); }
});
