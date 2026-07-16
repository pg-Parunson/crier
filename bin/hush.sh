#!/bin/sh
# Barge-in. The moment you start a new turn, whatever it's still saying stops —
# and whatever is mid-synthesis stays unsaid.
#
# Must always exit 0: on UserPromptSubmit a non-zero exit would block your prompt.
#
# The state path must mirror _state_dir() in announce.py exactly. macOS $TMPDIR
# ends with a slash, Python's gettempdir() strips it — normalize, or the pkill
# pattern below silently never matches.
if [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -d "${XDG_RUNTIME_DIR:-}" ]; then
  STATE="${XDG_RUNTIME_DIR%/}/agent-voice"
else
  TMP="${TMPDIR:-/tmp}"
  STATE="${TMP%/}/agent-voice-$(id -u)"
fi

PID_FILE="$STATE/play.pid"
[ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null

# Kill only players speaking OUR audio — every wav crier plays lives under $STATE.
pkill -f "$STATE" 2>/dev/null

# And suppress what hasn't started yet: a sentence mid-synthesis when you began
# typing would otherwise pop out two seconds into your next thought. perform()
# checks this marker's mtime right before pressing play.
mkdir -p "$STATE" 2>/dev/null
touch "$STATE/hush" 2>/dev/null
exit 0
