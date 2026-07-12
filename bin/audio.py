#!/usr/bin/env python3
"""Play a wav file, wherever you are.

macOS has exactly one answer (`afplay`). Linux has four, and which one works
depends on the sound server the distro happens to run — PipeWire on anything
recent, PulseAudio before that, bare ALSA on minimal installs. Guessing wrong
is silent failure, so we try each and keep the first that exists.

`ffplay` is last on purpose: it's the most likely to be installed and the least
likely to be what someone wants, since it's a video player wearing a disguise.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# (binary, args-before-file). Order is preference, not alphabet.
CANDIDATES = [
    ("afplay", []),                                    # macOS
    ("pw-play", []),                                   # PipeWire — the modern default
    ("paplay", []),                                    # PulseAudio
    ("aplay", ["-q"]),                                 # ALSA, no sound server
    ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),
]

PLAYERS = [c[0] for c in CANDIDATES]


def player() -> list[str] | None:
    override = os.environ.get("CRIER_PLAYER")
    if override:
        return override.split()
    for name, args in CANDIDATES:
        if shutil.which(name):
            return [name, *args]
    return None


def play(path: Path | str, pid_file: Path | None = None) -> int:
    """Play it. Returns the exit code, or -1 if there's nothing to play with."""
    cmd = player()
    if not cmd:
        return -1
    p = subprocess.Popen([*cmd, str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if pid_file:
        pid_file.write_text(str(p.pid))
    return p.wait()


if __name__ == "__main__":
    cmd = player()
    if not cmd:
        print("no audio player found. Install one of: " + ", ".join(PLAYERS[1:]),
              file=sys.stderr)
        print("  Debian/Ubuntu:  sudo apt install pipewire-bin   (or pulseaudio-utils, alsa-utils)",
              file=sys.stderr)
        sys.exit(1)
    if len(sys.argv) > 1:
        sys.exit(play(sys.argv[1]))
    print(" ".join(cmd))
