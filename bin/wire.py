#!/usr/bin/env python3
"""Register (or remove) the hooks in whichever agent you use.

Every agent gets the same two things: the end of a turn with the assistant's text,
and a permission request with the tool being approved. Only the spelling differs —
Claude Code and Codex agree exactly, Gemini and Cursor use other names. announce.py
normalizes them, so this file is a routing table, not four integrations.

    wire.py claude|codex|gemini|cursor [--remove]
"""

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANNOUNCE = f"{ROOT}/.venv/bin/python {ROOT}/bin/announce.py"
HUSH = f"{ROOT}/bin/hush.sh"
BOOT = f"nohup {ROOT}/bin/crier start >/dev/null 2>&1 & exit 0"

MARK = "__agent_voice__"  # so --remove knows what is ours


def cmd(c: str) -> list:
    return [{"hooks": [{"type": "command", "command": c}], MARK: True}]


AGENTS = {
    # Claude Code — ~/.claude/settings.json
    "claude": {
        "file": Path.home() / ".claude" / "settings.json",
        "at": ["hooks"],
        "hooks": {
            **{e: cmd(ANNOUNCE) for e in (
                "Stop", "StopFailure", "PermissionRequest", "Notification",
                "SubagentStart", "SubagentStop", "PreCompact")},
            "UserPromptSubmit": cmd(HUSH),   # barge-in
            "SessionStart": cmd(BOOT),
        },
    },
    # Codex CLI — ~/.codex/hooks.json. Same event names and fields as Claude Code.
    "codex": {
        "file": Path.home() / ".codex" / "hooks.json",
        "at": ["hooks"],
        "hooks": {
            **{e: cmd(ANNOUNCE) for e in (
                "Stop", "PermissionRequest", "SubagentStart", "SubagentStop", "PreCompact")},
            "UserPromptSubmit": cmd(HUSH),
            "SessionStart": cmd(BOOT),
        },
    },
    # Gemini CLI — ~/.gemini/settings.json. AfterAgent carries prompt_response.
    # Its hooks block the agent loop, which is fine: announce.py detaches in ~50ms.
    "gemini": {
        "file": Path.home() / ".gemini" / "settings.json",
        "at": ["hooks"],
        "hooks": {
            "AfterAgent": cmd(ANNOUNCE),
            "Notification": cmd(ANNOUNCE),
            "BeforeAgent": cmd(HUSH),
            "SessionStart": cmd(BOOT),
        },
    },
    # Cursor — ~/.cursor/hooks.json
    "cursor": {
        "file": Path.home() / ".cursor" / "hooks.json",
        "at": ["hooks"],
        "version": 1,
        "hooks": {
            "afterAgentResponse": [{"command": ANNOUNCE, MARK: True}],
            "beforeShellExecution": [{"command": ANNOUNCE, MARK: True}],
            "beforeSubmitPrompt": [{"command": HUSH, MARK: True}],
        },
    },
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in AGENTS:
        print(f"usage: wire.py {'|'.join(AGENTS)} [--remove]", file=sys.stderr)
        return 2

    name = sys.argv[1]
    remove = "--remove" in sys.argv
    spec = AGENTS[name]
    path: Path = spec["file"]

    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if path.exists():
        backup = path.with_suffix(f"{path.suffix}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(path, backup)
        print(f"  backup: {backup}")
        try:
            cfg = json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"  {path} is not valid JSON. Fix it first — nothing was changed.",
                  file=sys.stderr)
            return 1

    # Merge into whatever is already there. Other tools live in these files too.
    node = cfg
    for key in spec["at"]:
        node = node.setdefault(key, {})
    if "version" in spec:
        cfg.setdefault("version", spec["version"])

    if remove:
        for event in list(node):
            entries = [e for e in node[event] if not (isinstance(e, dict) and e.get(MARK))]
            if entries:
                node[event] = entries
            else:
                del node[event]
        print(f"  removed from {path}")
    else:
        node.update(spec["hooks"])
        print(f"  {len(spec['hooks'])} hooks → {path}")

    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
