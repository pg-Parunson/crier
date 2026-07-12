#!/bin/sh
# Barge-in. The moment you start a new turn, whatever it's still saying stops.
#
# Must always exit 0: on UserPromptSubmit a non-zero exit would block your prompt.
STATE="${TMPDIR:-/tmp}/agent-voice"
PID_FILE="$STATE/play.pid"
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null

# Whichever player this machine ended up with — see bin/audio.py.
for p in afplay pw-play paplay aplay ffplay; do
  pkill -x "$p" 2>/dev/null
done
exit 0
