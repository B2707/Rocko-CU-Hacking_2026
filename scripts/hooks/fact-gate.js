#!/usr/bin/env node
// PreToolUse[Edit|Write] fact-forcing gate — denies the FIRST touch of each
// code file per session with instructions to state impact facts, then allows
// the retry. Impact knowledge stays live (who imports this, what API changes)
// instead of being cached where it would go stale. Fail-open: never brick a seat.
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

const STATE_DIR = path.join(os.tmpdir(), 'team-os-gate');
const CODE_EXTS = new Set([
  '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.py', '.go', '.rs', '.rb',
  '.java', '.kt', '.swift', '.c', '.cc', '.cpp', '.h', '.hpp', '.css',
  '.scss', '.html', '.vue', '.svelte', '.sh', '.sql',
]);
const SKIP_PREFIXES = ['data/context/'];

function isGated(filePath, projectDir) {
  if (!filePath || !projectDir || !filePath.startsWith(projectDir)) return false;
  const rel = path.relative(projectDir, filePath);
  if (SKIP_PREFIXES.some((prefix) => rel.startsWith(prefix))) return false;
  if (path.basename(filePath).startsWith('.env')) return false;
  return CODE_EXTS.has(path.extname(filePath).toLowerCase());
}

function main(input) {
  const filePath = String((input.tool_input || {}).file_path || '');
  const projectDir = process.env.CLAUDE_PROJECT_DIR || input.cwd || '';
  if (!isGated(filePath, projectDir)) process.exit(0);

  const key = crypto.createHash('sha1').update(filePath).digest('hex').slice(0, 16);
  const marker = path.join(STATE_DIR, `${input.session_id}-${key}`);
  if (fs.existsSync(marker)) process.exit(0);

  fs.mkdirSync(STATE_DIR, { recursive: true });
  fs.writeFileSync(marker, filePath);
  const rel = path.relative(projectDir, filePath);
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: `[fact gate] First edit of ${rel} this session. `
        + 'Before retrying, state briefly: (1) who imports/calls this file, '
        + '(2) the API surface this change touches, (3) any data schemas affected, '
        + '(4) the line of your issue brief this serves. '
        + 'Then retry the SAME edit — it will pass.',
    },
  }));
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
    try { require('./hook-log').logHookError('fact-gate', err); } catch { /* best-effort */ }
    process.exit(0);
  }
});
