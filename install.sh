#!/usr/bin/env bash
# Set up the voice, generate the chimes, wire up your agent.
#
#   ./install.sh                          asks you three questions
#   ./install.sh --yes                    asks nothing; guesses from $LANG
#   ./install.sh --agent codex --lang ko --name "Jaeho" --yes
#   ./install.sh --no-hooks               engine only; wire it up yourself
#
# Model weights are never vendored into this repo. Supertonic fetches them to your
# cache on first run — its weights are OpenRAIL-M, and committing them would push
# that license's use restrictions onto everyone who clones this.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ROOT/.venv/bin/python"

step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

WIRE=1
for a in "$@"; do [[ "$a" == "--no-hooks" ]] && WIRE=0; done

step "Prerequisites"
[[ "$(uname)" == "Darwin" ]] || warn "Built and tested on macOS. Linux needs 'aplay' — playback is untested."
command -v uv >/dev/null || die "uv is required.  https://docs.astral.sh/uv/"
ok "uv $(uv --version | awk '{print $2}')"

step "Voice engine (Supertonic — local, offline, no API key)"
# System Python is often too new for ML wheels; uv pins one that works.
uv venv --python 3.11 "$ROOT/.venv" >/dev/null 2>&1 || die "could not create the virtualenv"
uv pip install --python "$PY" -q "supertonic[serve]" soundfile || die "could not install supertonic"
ok "supertonic installed"

step "Chimes"
"$PY" "$ROOT/bin/earcons.py" >/dev/null
ok "6 chimes synthesized → assets/earcons/  (not bundled — nothing to license)"

[[ -f "$ROOT/config.json" ]] || cp "$ROOT/config.default.json" "$ROOT/config.json"

if (( WIRE )); then
  # Asks three questions if someone's at a terminal — even under `curl | sh`, since
  # setup.py reads /dev/tty rather than stdin. If nobody's there (an agent doing the
  # install, CI), it takes the flags, guesses the rest, and says what it picked.
  AGENT="$("$PY" "$ROOT/bin/setup.py" "$@" | tail -1)"

  step "Wiring $AGENT"
  "$PY" "$ROOT/bin/wire.py" "$AGENT" || die "unknown agent: $AGENT"

  # Without this the agent never writes its spoken line, and crier falls back to
  # grabbing a sentence out of the reply. It works, but it's the lesser half of the
  # product — so it goes in by default rather than living in a hint at the bottom.
  "$PY" "$ROOT/bin/prompt.py" install --agent "$AGENT"
  ok "wired"
else
  warn "skipped hook registration"
fi

step "Starting the voice daemon"
"$ROOT/bin/crier" start

cat <<EOF

$(printf '\033[1mDone.\033[0m')  Restart your agent session, then:  crier demo

  crier voices              hear all 10 voices, then: crier voice M3
  crier setup               change language, agent, or what it calls you
  crier tone playful        plain | friendly | playful
  crier uninstall           removes the hooks, restores your settings

EOF
