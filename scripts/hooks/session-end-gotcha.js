#!/usr/bin/env node
// Stop hook — one nudge per session, and only when code was actually edited
// (fact-gate markers exist for this session): capture gotchas before stopping.
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const STATE_DIR = path.join(os.tmpdir(), 'team-os-gate');

function main(input) {
  if (input.stop_hook_active) process.exit(0); // never loop the agent

  const sessionId = String(input.session_id || '');
  if (!sessionId) process.exit(0);

  const nudgeMarker = path.join(STATE_DIR, `${sessionId}-gotcha-nudged`);
  if (fs.existsSync(nudgeMarker)) process.exit(0);

  const editedCode = fs.existsSync(STATE_DIR)
    && fs.readdirSync(STATE_DIR).some((name) => name.startsWith(`${sessionId}-`));
  if (!editedCode) process.exit(0);

  fs.mkdirSync(STATE_DIR, { recursive: true });
  fs.writeFileSync(nudgeMarker, String(Date.now()));
  process.stdout.write(JSON.stringify({
    decision: 'block',
    reason: 'Before finishing: did anything this session burn >10 minutes '
      + '(env quirk, API surprise, flaky tool)? If yes, capture it now: '
      + './scripts/task gotcha "<one-liner>". If not, say so and finish.',
  }));
  process.exit(0);
}

let raw = '';
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('end', () => {
  try { main(JSON.parse(raw)); }
  catch (err) {
    // Fail open, but record WHY. Lazy-require so a broken logger can't break
    // this hook.
    try { require('./hook-log').logHookError('session-end-gotcha', err); } catch { /* best-effort */ }
    process.exit(0);
  }
});
