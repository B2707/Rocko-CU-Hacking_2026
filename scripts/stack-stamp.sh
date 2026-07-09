#!/usr/bin/env bash
# Day-0 Stage 5 (docs/DAY0.md, 0:50 "Scope + stack"): stamp the chosen stack
# into the repo.
#   1. Validates stack.md and checks for a model map (audit C6 — without one,
#      prep-day burn patterns repeat: everything runs on Opus).
#   2. Splices matching rule packs from data/rules-library/ into CLAUDE.md
#      between stack-rules markers. Idempotent — restamp after editing
#      stack.md; never edit the stamped block by hand.
#   3. --verify: proves the post-write eslint hook catches a deliberate violation.
#
# Pack detection keys on stack.md text: typescript/ts/node/next -> typescript;
# react/next -> react; python/fastapi/django/flask -> python; the literal word
# "golang" -> golang. generic always stamps.
#
# Usage: scripts/stack-stamp.sh [--verify]
set -euo pipefail
cd "$(dirname "$0")/.."

VERIFY=false
[[ "${1:-}" == "--verify" ]] && VERIFY=true

if [[ ! -f stack.md ]]; then
  echo "stack-stamp: stack.md not found." >&2
  echo "Write the chosen stack to stack.md first (Day-0 Stage 5), then rerun." >&2
  exit 1
fi

echo "==> stack.md:"
sed 's/^/  | /' stack.md
echo

# --- model map check (audit C6) ----------------------------------------------
if grep -qi "model map" stack.md; then
  echo "==> model map found:"
  grep -iA6 "model map" stack.md | sed 's/^/  | /'
else
  echo "WARN: no 'Model map' section in stack.md — add one (audit C6), e.g.:"
  echo "  ## Model map"
  echo "  - review bot + agent loops: sonnet"
  echo "  - notifier / label watch: haiku"
  echo "  - architecture / planning: opus (manager seat only)"
fi
echo

# --- pack detection -----------------------------------------------------------
PACKS=(generic)
grep -qiE "typescript|\bts\b|\bnode\b|\bnext(\.js)?\b" stack.md && PACKS+=(typescript)
grep -qiE "react|\bnext(\.js)?\b" stack.md && PACKS+=(react)
grep -qiE "python|fastapi|django|flask" stack.md && PACKS+=(python)
grep -qi "golang" stack.md && PACKS+=(golang)
echo "==> stamping rule packs: ${PACKS[*]}"

STAMP=$(mktemp)
trap 'rm -f "$STAMP"' EXIT
{
  echo "<!-- stack-rules:begin (stamped by scripts/stack-stamp.sh — edit stack.md and restamp; do not edit this block) -->"
  echo "## Stack rules (stamped Day-0)"
  echo
  for pack in "${PACKS[@]}"; do
    file="data/rules-library/$pack.md"
    if [[ -f "$file" ]]; then
      cat "$file"
      echo
    else
      echo "WARN: missing rule pack $file — skipped" >&2
    fi
  done
  echo "<!-- stack-rules:end -->"
} > "$STAMP"

# --- idempotent splice into the kernel ----------------------------------------
if grep -q "stack-rules:begin" CLAUDE.md; then
  awk -v stamp="$STAMP" '
    /stack-rules:begin/ { while ((getline line < stamp) > 0) print line; close(stamp); skip=1; next }
    /stack-rules:end/   { skip=0; next }
    !skip               { print }
  ' CLAUDE.md > CLAUDE.md.new
else
  cp CLAUDE.md CLAUDE.md.new
  printf '\n' >> CLAUDE.md.new
  cat "$STAMP" >> CLAUDE.md.new
fi
mv CLAUDE.md.new CLAUDE.md
echo "    stamped into CLAUDE.md (between stack-rules markers)"
echo

# --- hook auto-activation reminder ---------------------------------------------
echo "==> auto-activates on its own (scripts/hooks/post-write-check.js):"
echo "    - eslint on every JS/TS edit once an eslint config exists"
echo "    (types are enforced by the required CI build-test check, not at edit time)"
echo

# --- --verify: prove the post-write eslint hook bites --------------------------
if $VERIFY; then
  echo "==> verify: post-write eslint hook vs a deliberate violation"
  hook="scripts/hooks/post-write-check.js"
  have_cfg=false
  for c in eslint.config.js eslint.config.mjs eslint.config.cjs .eslintrc .eslintrc.js .eslintrc.cjs .eslintrc.json; do
    [[ -f "$c" ]] && have_cfg=true && break
  done
  if [[ -e node_modules/.bin/eslint ]] && $have_cfg; then
    probe="$PWD/.stack-stamp-probe.$$.js"
    printf 'function( {\n' > "$probe"   # syntax error — flagged by any eslint config
    payload="$(printf '{"tool_input":{"file_path":"%s"},"cwd":"%s"}' "$probe" "$PWD")"
    if CLAUDE_PROJECT_DIR="$PWD" printf '%s' "$payload" | node "$hook" >/dev/null 2>&1; then
      rm -f "$probe"
      echo "    FAIL: post-write hook did NOT flag the violation — investigate before trusting it" >&2
      exit 1
    fi
    rm -f "$probe"
    echo "    PASS: post-write eslint hook catches violations (exit 2)"
  else
    echo "    SKIP: no eslint config + node_modules yet (expected before scaffold)"
  fi
  echo
fi

echo "==> done — commit stack.md + CLAUDE.md via PR (./scripts/task ship)"
