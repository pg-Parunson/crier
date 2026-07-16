#!/usr/bin/env python3
"""crier doctor — why isn't it speaking?

Every silent-failure path in crier is deliberate: a broken announcement must never
break a coding session, so the hook swallows errors and exits 0. The cost is that
"installed fine but never speaks" is invisible. This is where that cost gets paid
back: one command that checks every link in the chain and says which one is broken,
in order, with the fix next to it.

Exit code 0 when everything passes, 1 otherwise — so it's scriptable.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
import audio  # noqa: E402
import cfg as cfgmod  # noqa: E402

LOG_PATH = ROOT / ".venv" / "crier.log"
GREEN, RED, YELLOW, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
failed = 0


def ok(label, detail=""):
    print(f"  {GREEN}✓{OFF} {label}" + (f"  {DIM}{detail}{OFF}" if detail else ""))


def bad(label, fix):
    global failed
    failed += 1
    print(f"  {RED}✗{OFF} {label}")
    print(f"      → {fix}")


def warn(label, detail):
    print(f"  {YELLOW}!{OFF} {label}  {DIM}{detail}{OFF}")


def main() -> int:
    print(f"\ncrier doctor · {ROOT}")
    try:
        ver = subprocess.run(["git", "-C", str(ROOT), "describe", "--tags", "--always"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        print(f"version: {ver}\n")
    except Exception:
        print()

    # 1. config
    cfg = cfgmod.load(ROOT)   # merged view — what announce.py actually sees
    try:
        json.loads((ROOT / "config.json").read_text())
        ok("config.json parses",
           f"lang={cfg.get('lang')} tone={cfg.get('tone')} voice={cfg.get('voice')}")
    except FileNotFoundError:
        warn("config.json missing — running on pure defaults", "run: crier setup")
    except json.JSONDecodeError as e:
        bad(f"config.json is broken JSON (line {e.lineno}) — defaults are in effect",
            "fix the syntax, or delete it and run: crier setup")

    if cfg.get("muted"):
        warn("muted is ON", "that's why it's quiet — run: crier unmute")

    # 2. venv + engine
    py = ROOT / ".venv" / "bin" / "python"
    if py.exists():
        ok("python venv", str(py.parent.parent.name) + "/.venv")
    else:
        bad("python venv missing", "run: ./install.sh --no-hooks   (from ~/.crier)")

    # 3. voice model cache
    cache = Path.home() / ".cache" / "supertonic3"
    if cache.exists() and any(cache.iterdir()):
        size = sum(f.stat().st_size for f in cache.rglob("*") if f.is_file())
        ok("voice model cached", f"~{size // 1_000_000}MB in ~/.cache/supertonic3")
    else:
        warn("voice model not downloaded yet",
             "first `crier start` fetches it — needs network access to huggingface.co")

    # 4. daemon
    port = int(cfg.get("port", 7788))
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            ok("daemon listening", f"127.0.0.1:{port}")
    except OSError:
        bad(f"daemon not running on port {port}", "run: crier start   (then check ~/.crier/.venv/supertonic.log)")

    # 5. audio player
    player = audio.player()
    if player:
        ok("audio player", " ".join(player))
    else:
        bad("no audio player found",
            "macOS ships afplay; on Linux install one: sudo apt install pipewire-bin  (or pulseaudio-utils / alsa-utils)")

    # 6. hooks actually registered
    hook_files = {
        "Claude Code": Path.home() / ".claude" / "settings.json",
        "Codex": Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "hooks.json",
        "Gemini": Path.home() / ".gemini" / "settings.json",
        "Cursor": Path.home() / ".cursor" / "hooks.json",
    }
    wired = []
    for name, f in hook_files.items():
        try:
            if "announce.py" in f.read_text():
                wired.append(name)
        except OSError:
            pass
    if wired:
        ok("hooks registered", " · ".join(wired))
    else:
        bad("no agent has crier hooks", "run: crier install   (or: crier install codex|gemini|cursor)")

    # 7. the [say] instruction
    spots = [Path.home() / ".claude" / "rules" / "crier.md",
             Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "AGENTS.md",
             Path.home() / ".gemini" / "GEMINI.md"]
    marker = cfg.get("marker", "[say]")
    if any(s.exists() and "crier:begin" in s.read_text() for s in spots):
        ok("spoken-line instruction installed", f"marker {marker}")
    else:
        warn("spoken-line instruction not installed",
             "crier falls back to extracting a sentence — `crier prompt install` makes the agent write a better one")

    # 8. recent errors
    logf = LOG_PATH
    if logf.exists() and logf.stat().st_size:
        lines = logf.read_text().strip().splitlines()
        recent = [l for l in lines if l][-3:]
        age = time.time() - logf.stat().st_mtime
        if age < 3600:
            warn(f"errors logged recently ({len(lines)} total)", recent[-1][:100])
        else:
            ok("error log quiet", f"last entry {int(age // 3600)}h ago")
    else:
        ok("no errors logged")

    print()
    if failed:
        print(f"  {failed} problem(s). Fix the first ✗ — the chain breaks at the earliest link.\n")
        return 1
    print("  Everything checks out. If it's still silent, run `crier demo` and listen —\n"
          "  and if THAT is silent, your output device/volume is the last suspect.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
