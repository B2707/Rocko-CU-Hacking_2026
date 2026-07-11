#!/usr/bin/env bash
# heartbeat.sh — post a seat presence beat to the team console so the wall's
# seat panels show REAL activity (who's on, when they last acted).
#
# Usage:
#   scripts/heartbeat.sh [note]          one beat (fired by scripts/task on
#                                        every command — you rarely run this)
#   scripts/heartbeat.sh --loop [secs]   beat forever (manager cockpit; 300s default)
#
# Needs TEAM_SEAT + TEAM_HEARTBEAT_SECRET (from .env). Console URL defaults to
# the stable prod alias; override with CONSOLE_URL. Always best-effort: a dead
# console must never block or slow team commands.
set -uo pipefail
cd "$(dirname "$0")/.."
_seat_env="${TEAM_SEAT:-}"
[ -f .env ] && { set -a; . ./.env 2>/dev/null || true; set +a; }
[ -n "$_seat_env" ] && TEAM_SEAT="$_seat_env"
: "${CONSOLE_URL:=https://hackathon-console.vercel.app}"
[ -n "${TEAM_SEAT:-}" ] || { echo "heartbeat: TEAM_SEAT not set — fill .env" >&2; exit 1; }
[ -n "${TEAM_HEARTBEAT_SECRET:-}" ] || { echo "heartbeat: TEAM_HEARTBEAT_SECRET not set — console features off" >&2; exit 1; }
seat=$(printf '%s' "$TEAM_SEAT" | tr '[:upper:]' '[:lower:]')

beat() { # [note] — sanitized; server caps at 120 chars
  local note; note=$(printf '%s' "${1:-}" | tr -d '"\\' | cut -c1-120)
  curl -s -m 10 -X POST "$CONSOLE_URL/api/heartbeat" \
    -H "x-team-secret: $TEAM_HEARTBEAT_SECRET" \
    -H "content-type: application/json" \
    -d "{\"seat\":\"$seat\"${note:+,\"note\":\"$note\"}}" >/dev/null 2>&1 || true
}

if [ "${1:-}" = "--loop" ]; then
  every="${2:-300}"
  echo "heartbeat: looping every ${every}s as seat '$seat' (Ctrl-C stops)"
  while :; do beat "cockpit up"; sleep "$every"; done
fi
beat "${1:-}"
