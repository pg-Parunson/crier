#!/usr/bin/env python3
"""Register (or remove) the hooks in whichever agent you use.

Every agent gets the same two things: the end of a turn with the assistant's text,
and a permission request with the tool being approved. Only the spelling differs —
Claude Code and Codex agree exactly, Gemini and Cursor use other names. announce.py
normalizes them, so this file is a routing table, not four integrations.

    wire.py claude|codex|gemini|cursor [--remove]
"""

import json
import os
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


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


CRIER = f"{ROOT}/bin/crier"
HINT = "voice M3 | lang ko | tone playful | name Jaeho | mute | unmute | voices | demo"
BLURB = "Configure crier — voice, language, tone, or mute it"

# `/crier` from inside a session. Claude and Gemini run the shell at expansion time
# and paste the output straight in, so nothing reaches the model and nothing is
# spent. Codex can't do that — it has no expansion-time shell — so there the command
# asks the model to run it, which costs a tool call. That's the best it offers.
#
# The absolute path matters: the agent's shell may not have ~/.local/bin on PATH.
COMMANDS = {
    "claude": (
        Path.home() / ".claude" / "commands" / "crier.md",
        f"""---
description: {BLURB}
argument-hint: [{HINT}]
allowed-tools: Bash({CRIER} *)
disable-model-invocation: true
---
!`{CRIER} $ARGUMENTS`
""",
    ),
    "gemini": (
        Path.home() / ".gemini" / "commands" / "crier.toml",
        f'''description = "{BLURB}"
prompt = """
!{{{CRIER} {{{{args}}}}}}
"""
''',
    ),
    "codex": (
        codex_home() / "prompts" / "crier.md",
        f"""---
description: {BLURB}
argument-hint: [{HINT}]
---
Run this and show me its output verbatim. Don't explain it, don't add commentary.

```
{CRIER} $ARGUMENTS
```
""",
    ),
}


def command_file(agent: str, remove: bool) -> None:
    if agent not in COMMANDS:
        return  # cursor has no user-level custom commands
    path, body = COMMANDS[agent]
    if remove:
        path.unlink(missing_ok=True)
        print(f"  /crier removed")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    print(f"  /crier → {path}")

    if agent == "gemini":
        # Otherwise Gemini asks permission every single time the command runs.
        s = Path.home() / ".gemini" / "settings.json"
        cfg = {}
        if s.exists():
            try:
                cfg = json.loads(s.read_text())
            except json.JSONDecodeError:
                return
        allowed = cfg.setdefault("tools", {}).setdefault("allowed", [])
        entry = f"run_shell_command({CRIER})"
        if entry not in allowed:
            allowed.append(entry)
            s.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")


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
    command_file(name, remove)
    return 0


if __name__ == "__main__":
    sys.exit(main())
