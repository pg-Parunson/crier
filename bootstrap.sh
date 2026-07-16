#!/bin/sh
# One-line install.
#
#   curl -fsSL https://raw.githubusercontent.com/pg-Parunson/crier/main/bootstrap.sh | sh
#   curl -fsSL .../bootstrap.sh | sh -s -- codex        # pick your agent
#
# Clones to ~/.crier, sets everything up, and puts `crier` on your PATH.
#
# POSIX sh only — no bashisms. We tell people to pipe this into `sh`, and on Linux
# that's dash, which dies on `set -o pipefail` before printing a single line. The
# installer it calls can use bash; this file cannot.
set -eu

REPO="https://github.com/pg-Parunson/crier"
HOME_DIR="${CRIER_HOME:-$HOME/.crier}"
BIN_DIR="${CRIER_BIN:-$HOME/.local/bin}"

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

printf '\n\033[1mcrier\033[0m — your coding agent tells you what happened\n\n'

if ! command -v git >/dev/null; then
  case "$(uname)" in
    Darwin) die "git is required:  xcode-select --install" ;;
    *)      die "git is required:  sudo apt install git   (or your distro's equivalent)" ;;
  esac
fi

# Linux needs something that can actually make a sound. macOS always can.
if [ "$(uname)" != "Darwin" ]; then
  HAVE_PLAYER=""
  for p in pw-play paplay aplay ffplay; do
    command -v "$p" >/dev/null && HAVE_PLAYER="$p" && break
  done
  [ -n "$HAVE_PLAYER" ] || die "no audio player found. Install one:
      sudo apt install pipewire-bin      # or: pulseaudio-utils, alsa-utils"
fi

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

# Pin to the newest release tag so a fresh install gets a version somebody
# deliberately cut, not whatever happens to be on main this minute. The tag is
# read from the remote BEFORE cloning: a depth-1 clone only carries tags that
# point at the tip, so `git describe` after the fact can't be trusted. No tags
# yet (or ls-remote blocked) → fall back to main, same as before.
TAG="$(git ls-remote --tags --refs --sort=-v:refname "$REPO" 2>/dev/null | head -n1 | sed 's|.*refs/tags/||')"

if [ -d "$HOME_DIR/.git" ]; then
  # A previous install may sit on a detached tag checkout, where `git pull` is
  # fatal ("not currently on a branch") — fetch+checkout works from any state.
  git -C "$HOME_DIR" fetch --tags --quiet origin
  if [ -n "$TAG" ]; then
    git -C "$HOME_DIR" checkout --quiet "$TAG"
  else
    git -C "$HOME_DIR" checkout --quiet main && git -C "$HOME_DIR" pull --ff-only --quiet
  fi
  ok "updated $HOME_DIR${TAG:+ → $TAG}"
else
  if [ -n "$TAG" ]; then
    git clone --quiet --depth 1 --branch "$TAG" "$REPO" "$HOME_DIR"
  else
    git clone --quiet --depth 1 "$REPO" "$HOME_DIR"
  fi
  ok "cloned to $HOME_DIR${TAG:+ ($TAG)}"
fi

# Forward everything, not just the first word: `sh -s -- codex` and
# `sh -s -- --agent codex --lang ko --yes` both have to reach the installer intact.
"$HOME_DIR/install.sh" "$@"

mkdir -p "$BIN_DIR"
ln -sf "$HOME_DIR/bin/crier" "$BIN_DIR/crier"
ok "crier → $BIN_DIR/crier"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) printf '\n  \033[33m!\033[0m %s is not on your PATH. Add this to your shell profile:\n\n      export PATH="%s:$PATH"\n' "$BIN_DIR" "$BIN_DIR" ;;
esac

printf '\n  Restart your agent session, then:  \033[1mcrier demo\033[0m\n\n'
