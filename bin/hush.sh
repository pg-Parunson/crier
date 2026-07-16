#!/bin/sh
# Barge-in. The moment you start a new turn, whatever it's still saying stops.
#
# Must always exit 0: on UserPromptSubmit a non-zero exit would block your prompt.
#
# The state path must mirror _state_dir() in announce.py exactly — per-user, XDG
# first. Nested ${A:-${B:-c}} default expansion is a classic dash pitfall, so the
# two branches are spelled out.
if [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -d "${XDG_RUNTIME_DIR:-}" ]; then
  STATE="$XDG_RUNTIME_DIR/agent-voice"
else
  STATE="${TMPDIR:-/tmp}/agent-voice-$(id -u)"
fi

PID_FILE="$STATE/play.pid"
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null

# Kill only players speaking OUR audio: every wav crier plays lives under $STATE,
# so match on that path instead of nuking whatever afplay/aplay the user happens
# to be running for their own reasons.
pkill -f "$STATE" 2>/dev/null
exit 0
