#!/usr/bin/env node
// Shared fail-open error logger for the PreToolUse/PostToolUse/Stop hooks.
// Hooks fail open (exit 0) on any internal error so a bug never bricks a seat —
// but a fully silent failure hides a disabled gate. Each hook calls this from
// its top-level catch to append the error to a debug log, so a regression is
// diagnosable (canon: workflow-enforcement-and-hooks.md — debug-log to a file,
// never stdout/stderr). Best-effort: this never throws, and each hook
// lazy-requires it so a broken logger can't disable the hook's main path.
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

// Same dir the gate hooks already use for per-session markers — outside the
// repo (tmp), so the log is never committed.
const LOG_DIR = path.join(os.tmpdir(), 'team-os-gate');
const LOG_FILE = path.join(LOG_DIR, 'hook-errors.log');

function logHookError(hook, err) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    const detail = (err && err.stack) || String(err);
    fs.appendFileSync(LOG_FILE, `${new Date().toISOString()} [${hook}] ${detail}\n`);
  } catch {
    /* best-effort: logging must never break the fail-open path */
  }
}

module.exports = { logHookError };
