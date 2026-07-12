#!/usr/bin/env python3
"""Install the one instruction that makes the agent write its own spoken line.

This is the whole "let an LLM write the speech" mechanism, and it costs nothing.
There is no second API call and no second key: the model that just did the work —
the only thing in the system that knows what the turn was actually about — appends
one `[say]` line, and the Stop hook reads it. A handful of output tokens.

The tone rides along in the same instruction, which is why a persona is free. It's
a sentence in a prompt, not a model.

    prompt.py install [--file PATH]
    prompt.py remove  [--file PATH]
    prompt.py show
"""

import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text())
LOCALES = json.loads((ROOT / "locales.json").read_text())

BEGIN = "<!-- agent-voice:begin -->"
END = "<!-- agent-voice:end -->"

DEFAULT_TARGET = Path.home() / ".claude" / "CLAUDE.md"


def snippet() -> str:
    loc = LOCALES.get(CFG.get("lang", "en")) or LOCALES["en"]
    p = loc["prompt"]
    tone = loc["tone_hint"].get(CFG.get("tone", "plain"), "")
    marker = CFG["marker"]

    rules = "\n".join(f"- {r}" for r in p["rules"])
    return "\n".join([
        BEGIN,
        f"## {p['title']}",
        "",
        p["lead"].format(marker=marker),
        "",
        rules,
        f"- Tone / 말투: {tone}",
        "",
        f"`{marker} {p['example']}`",
        END,
    ])


def strip(text: str) -> str:
    return re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n*", "", text, flags=re.S)


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "show"
    target = DEFAULT_TARGET
    if "--file" in args:
        target = Path(args[args.index("--file") + 1]).expanduser()

    if cmd == "show":
        print(snippet())
        installed = target.exists() and BEGIN in target.read_text()
        print(f"\n{'installed' if installed else 'not installed'}: {target}")
        return 0

    if cmd not in ("install", "remove"):
        print("usage: prompt.py {install|remove|show} [--file PATH]", file=sys.stderr)
        return 2

    target.parent.mkdir(parents=True, exist_ok=True)
    old = target.read_text() if target.exists() else ""

    if old:
        backup = target.with_suffix(f"{target.suffix}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(target, backup)
        print(f"backup: {backup}")

    body = strip(old).rstrip()
    if cmd == "install":
        target.write_text(f"{body}\n\n{snippet()}\n" if body else f"{snippet()}\n")
        print(f"installed → {target}   (lang={CFG.get('lang')}, tone={CFG.get('tone')})")
    else:
        target.write_text(f"{body}\n" if body else "")
        print(f"removed → {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
