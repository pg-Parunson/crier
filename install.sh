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
ARGS=()
PREV=""
for a in "$@"; do
  # A word right after a value-taking flag is that flag's value — never a command of
  # its own. Without this, `--agent gemini` rewrote itself into `--agent --agent gemini`.
  case "$PREV" in
    --agent|--lang|--name|--voice|--tone) ARGS+=("$a"); PREV="$a"; continue ;;
  esac
  case "$a" in
    --no-hooks) WIRE=0 ;;
    # The README says `sh -s -- codex`, so a bare agent name has to work. setup.py
    # only speaks flags, and silently defaulted a Codex user to Claude.
    claude|codex|gemini|cursor) ARGS+=(--agent "$a") ;;
    *) ARGS+=("$a") ;;
  esac
  PREV="$a"
done

step "Prerequisites"
[[ "$(uname)" == "Darwin" ]] || warn "Built and tested on macOS. Linux needs 'aplay' — playback is untested."
command -v uv >/dev/null || die "uv is required.  https://docs.astral.sh/uv/"
ok "uv $(uv --version | awk '{print $2}')"

step "Voice engine (Supertonic — local, offline, no API key)"
# System Python is often too new for ML wheels; uv pins one that works.
# `uv venv` refuses to overwrite, so re-running the installer — which is exactly what
# `crier update` and a second bootstrap do — would die here on an existing install.
if [[ ! -x "$PY" ]]; then
  uv venv --python 3.11 "$ROOT/.venv" >/dev/null 2>&1 || die "could not create the virtualenv"
fi
uv pip install --python "$PY" -q "supertonic[serve]" soundfile || die "could not install supertonic"
ok "supertonic installed"

step "Chimes"
"$PY" "$ROOT/bin/earcons.py" >/dev/null
ok "6 chimes synthesized → assets/earcons/  (not bundled — nothing to license)"

if [[ ! -f "$ROOT/config.json" ]]; then
  # Guess the language from the locale *while creating* the config. Copying the
  # defaults first and detecting afterwards doesn't work: setup.py takes the config's
  # value if there is one, so the "en" it just copied in wins and a Japanese user
  # gets announcements in English.
  case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in
    ko*) GUESS=ko ;;
    ja*) GUESS=ja ;;
    *)   GUESS=en ;;
  esac
  "$PY" - "$ROOT" "$GUESS" <<'PY'
import json, pathlib, sys
root, lang = pathlib.Path(sys.argv[1]), sys.argv[2]
cfg = json.loads((root / "config.default.json").read_text())
cfg["lang"] = lang
(root / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
PY
fi

if (( WIRE )); then
  # Asks three questions if someone's at a terminal — even under `curl | sh`, since
  # setup.py reads /dev/tty rather than stdin. If nobody's there (an agent doing the
  # install, CI), it takes the flags, guesses the rest, and says what it picked.
  AGENT="$("$PY" "$ROOT/bin/setup.py" "${ARGS[@]+"${ARGS[@]}"}" | tail -1)"

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
