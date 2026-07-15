#!/usr/bin/env python3
"""Install the one instruction that makes the agent write its own spoken line.

This is the whole "let an LLM write the speech" mechanism, and it costs nothing.
No second API call, no second key: the model that just did the work — the only
thing that knows what the turn was about — appends one `[say]` line, and the Stop
hook reads it. A handful of output tokens.

The tone rides along in the same instruction, which is why a persona is free: it's
a sentence in a prompt, not a model.

Where it goes differs per agent, and the differences bite:

- **Claude Code** reads `~/.claude/rules/*.md` for every project. Dropping our own
  file there beats editing CLAUDE.md — no merge, and removal is one unlink.
- **Codex** reads `~/.codex/AGENTS.md` — *unless* `AGENTS.override.md` exists next
  to it, in which case AGENTS.md is ignored wholesale. Write to the wrong one and
  the feature silently does nothing.
- **Gemini** reads `~/.gemini/GEMINI.md`, but `context.fileName` in settings.json
  can rename it, so we read that first rather than assume.
- **Cursor** has no user-level instruction file at all. Its User Rules live in the
  app's own storage. We print the text and let the human paste it.

    prompt.py install|remove|show [--agent claude|codex|gemini|cursor]
"""

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text())
LOCALES = json.loads((ROOT / "locales.json").read_text())

BEGIN = "<!-- crier:begin -->"
END = "<!-- crier:end -->"
LEGACY = ("<!-- agent-voice:begin -->", "<!-- agent-voice:end -->")


def snippet(fenced: bool = False) -> str:
    loc = LOCALES.get(CFG.get("lang", "en")) or LOCALES["en"]
    p = loc["prompt"]
    _alias = {"plain": "2", "friendly": "3", "playful": "4"}
    _lvl = _alias.get(str(CFG.get("tone", "3")), str(CFG.get("tone", "3")))
    tone = loc["tone_hint"].get(_lvl, loc["tone_hint"].get("3", ""))
    marker = CFG["marker"]

    body = "\n".join([
        f"## {p['title']}",
        "",
        p["lead"].format(marker=marker),
        "",
        *[f"- {r}" for r in p["rules"]],
        f"- Tone: {tone}",
        "",
        f"`{marker} {p['example']}`",
    ])
    return body if fenced else f"{BEGIN}\n{body}\n{END}"


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def gemini_file() -> Path:
    home = Path(os.environ.get("GEMINI_CLI_HOME") or Path.home()) / ".gemini"
    name = "GEMINI.md"
    try:  # the user may have renamed it, and then GEMINI.md is never read
        ctx = json.loads((home / "settings.json").read_text()).get("context", {}).get("fileName")
        if isinstance(ctx, list) and ctx:
            name = ctx[0]
        elif isinstance(ctx, str):
            name = ctx
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return home / name


def target(agent: str) -> Path | None:
    """The file to write, or None if the agent has no such file."""
    if agent == "claude":
        return Path.home() / ".claude" / "rules" / "crier.md"
    if agent == "codex":
        home = codex_home()
        override = home / "AGENTS.override.md"
        # Codex reads only the FIRST non-empty of these two. If the override exists,
        # AGENTS.md is dead to it — so that's where our block has to go.
        return override if override.exists() else home / "AGENTS.md"
    if agent == "gemini":
        return gemini_file()
    return None  # cursor: user rules live in the app, not on disk


def strip(text: str) -> str:
    for begin, end in ((BEGIN, END), LEGACY):
        text = re.sub(re.escape(begin) + r".*?" + re.escape(end) + r"\n*", "", text, flags=re.S)
    return text


def manual(agent: str) -> None:
    print(f"\n  {agent} keeps its user-level instructions inside the app, not in a file.")
    print("  Paste this into Cursor Settings → Customize → Rules:\n")
    print("  " + "\n  ".join(snippet(fenced=True).splitlines()))
    print("\n  (Skip it if you'd rather not — crier falls back to picking a line"
          "\n   out of the reply itself. The agent writes a better one.)\n")


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "show"
    agent = args[args.index("--agent") + 1] if "--agent" in args else "claude"

    if cmd not in ("install", "remove", "show"):
        print("usage: prompt.py {install|remove|show} [--agent claude|codex|gemini|cursor]",
              file=sys.stderr)
        return 2

    path = target(agent)
    if path is None:
        if cmd == "install":
            manual(agent)
        return 0

    if cmd == "show":
        print(snippet())
        installed = path.exists() and BEGIN in path.read_text()
        print(f"\n{'installed' if installed else 'not installed'}: {path}")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text() if path.exists() else ""
    if old:
        backup = path.with_suffix(f"{path.suffix}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(path, backup)
        print(f"  backup: {backup}")

    body = strip(old).rstrip()

    if cmd == "remove":
        # Our own file under rules/ has nothing else in it — take the whole thing.
        if agent == "claude" and not body:
            path.unlink(missing_ok=True)
        else:
            path.write_text(f"{body}\n" if body else "")
        print(f"  removed → {path}")
        return 0

    path.write_text(f"{body}\n\n{snippet()}\n" if body else f"{snippet()}\n")
    print(f"  spoken-line instruction → {path}   (lang={CFG['lang']}, tone={CFG['tone']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
