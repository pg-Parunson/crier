#!/bin/sh
# Barge-in. The moment you start a new turn, whatever it's still saying stops.
#
# Must always exit 0: on UserPromptSubmit a non-zero exit would block your prompt.
STATE="${TMPDIR:-/tmp}/agent-voice"
PID_FILE="$STATE/play.pid"
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null
pkill -x afplay 2>/dev/null
pkill -x aplay 2>/dev/null
exit 0
