#!/usr/bin/env bash
# One-line install.
#
#   curl -fsSL https://raw.githubusercontent.com/pg-Parunson/crier/main/bootstrap.sh | sh
#   curl -fsSL .../bootstrap.sh | sh -s -- codex        # pick your agent
#
# Clones to ~/.crier, sets everything up, and puts `crier` on your PATH.
set -euo pipefail

REPO="https://github.com/pg-Parunson/crier"
HOME_DIR="${CRIER_HOME:-$HOME/.crier}"
BIN_DIR="${CRIER_BIN:-$HOME/.local/bin}"
AGENT="${1:-claude}"

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

printf '\n\033[1mcrier\033[0m — your coding agent tells you what happened\n\n'

command -v git >/dev/null || die "git is required. Install Xcode Command Line Tools: xcode-select --install"

# uv runs the Python that runs the voice. Most people who land here don't have it and
# shouldn't have to care — so fetch it rather than bouncing them to another README.
# (Piped into sh, we have no stdin left to ask a question with, so we say what we're
# doing instead of asking.)
if ! command -v uv >/dev/null; then
  printf '  uv is missing — installing it from astral.sh\n'
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || die "could not install uv"
  # Its installer puts uv on PATH for *new* shells; this one is already running.
  for d in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
    [ -x "$d/uv" ] && PATH="$d:$PATH"
  done
  export PATH
  command -v uv >/dev/null || die "uv installed but isn't on PATH — open a new terminal and re-run this"
fi
ok "uv $(uv --version | awk '{print $2}')"

if [ -d "$HOME_DIR/.git" ]; then
  git -C "$HOME_DIR" pull --ff-only --quiet
  ok "updated $HOME_DIR"
else
  git clone --quiet --depth 1 "$REPO" "$HOME_DIR"
  ok "cloned to $HOME_DIR"
fi

"$HOME_DIR/install.sh" "$AGENT"

mkdir -p "$BIN_DIR"
ln -sf "$HOME_DIR/bin/crier" "$BIN_DIR/crier"
ok "crier → $BIN_DIR/crier"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) printf '\n  \033[33m!\033[0m %s is not on your PATH. Add this to your shell profile:\n\n      export PATH="%s:$PATH"\n' "$BIN_DIR" "$BIN_DIR" ;;
esac

printf '\n  Restart your agent session, then:  \033[1mcrier demo\033[0m\n\n'
