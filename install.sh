#!/usr/bin/env bash
# Set up the voice, generate the chimes, wire up your agent.
#
#   ./install.sh                 # Claude Code (default)
#   ./install.sh codex           # Codex CLI
#   ./install.sh gemini          # Gemini CLI
#   ./install.sh cursor          # Cursor
#   ./install.sh --no-hooks      # engine only; wire it up yourself
#
# Model weights are never vendored into this repo. Supertonic fetches them to your
# cache on first run — its weights are OpenRAIL-M, and committing them would push
# that license's use restrictions onto everyone who clones this.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT="${1:-claude}"

step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

step "Prerequisites"
[[ "$(uname)" == "Darwin" ]] || warn "Built and tested on macOS. Linux needs 'aplay' — playback is untested."
command -v uv >/dev/null || die "uv is required.  brew install uv   (https://docs.astral.sh/uv/)"
ok "uv $(uv --version | awk '{print $2}')"

step "Voice engine (Supertonic — local, offline, no API key)"
# System Python is often too new for ML wheels; uv pins one that works.
uv venv --python 3.11 "$ROOT/.venv" >/dev/null 2>&1 || die "could not create the virtualenv"
uv pip install --python "$ROOT/.venv/bin/python" -q "supertonic[serve]" soundfile \
  || die "could not install supertonic"
ok "supertonic installed"

step "Chimes"
"$ROOT/.venv/bin/python" "$ROOT/bin/earcons.py" >/dev/null
ok "6 chimes synthesized → assets/earcons/  (not bundled — nothing to license)"

step "Config"
if [[ -f "$ROOT/config.json" ]]; then
  ok "config.json exists — left alone"
else
  cp "$ROOT/config.default.json" "$ROOT/config.json"
  ok "config.json created  (lang=ko, voice=F2 — change with 'bin/crier lang en')"
fi

if [[ "$AGENT" == "--no-hooks" ]]; then
  warn "skipped hook registration"
else
  step "Wiring $AGENT"
  "$ROOT/.venv/bin/python" "$ROOT/bin/wire.py" "$AGENT" || die "unknown agent: $AGENT"
  ok "wired"
fi

step "Starting the voice daemon"
"$ROOT/bin/crier" start

cat <<EOF

$(printf '\033[1mDone.\033[0m')  Restart your agent session so it picks up the hooks.

  crier      demo                hear every event
  crier      voices              hear all 10 voices, then: bin/crier voice M3
  crier      lang en             ko | en | ja
  crier      tone playful        plain | friendly | playful
  crier      name "Jaeho"        it'll use your name now and then
  crier      prompt install      let the agent write its own spoken line (recommended)

EOF
