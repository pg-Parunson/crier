#!/usr/bin/env python3
"""Ask the three things crier can't guess, then write them down.

Run from install.sh, or any time afterwards as `crier setup`.

Two ways in:

- **A human at a terminal.** We read from /dev/tty, not stdin — the installer is
  usually `curl … | sh`, which has already eaten stdin, so a plain input() would
  read the rest of the shell script as an answer.
- **Nobody at a terminal** (an agent installing this for you, CI, a Dockerfile).
  Then we ask nothing, take the flags we were given, guess the rest from $LANG,
  and say what we picked.

    setup.py [--lang ko|en|ja] [--agent claude|codex|gemini|cursor]
             [--name "Jaeho"] [--voice F2] [--tone plain|friendly|playful]
             [--yes]   never prompt, even with a terminal
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config.json"
LOCALES = json.loads((ROOT / "locales.json").read_text())

LANGS = [("en", "English"), ("ko", "한국어"), ("ja", "日本語")]
AGENTS = [
    ("claude", "Claude Code"),
    ("codex", "Codex CLI"),
    ("gemini", "Gemini CLI"),
    ("cursor", "Cursor"),
]

ASK = {
    "en": {
        "lang": "What language should it speak?",
        "agent": "Which agent are you wiring up?",
        "name": "What should it call you?  (blank = don't use a name)",
        "name_hint": "It'll use your name now and then — not every time.",
        "done": "Set. Change any of it later with:  crier lang · crier voice · crier name",
        "voice": "Pick a voice with `crier voices` when you're ready — F2 for now.",
    },
    "ko": {
        "lang": "어떤 언어로 말할까요?",
        "agent": "어떤 에이전트에 연결할까요?",
        "name": "뭐라고 불러드릴까요?  (비우면 이름을 안 부릅니다)",
        "name_hint": "매번은 아니고 가끔 불러줍니다.",
        "done": "완료. 나중에 바꾸려면:  crier lang · crier voice · crier name",
        "voice": "목소리는 나중에 `crier voices`로 골라주세요. 지금은 F2입니다.",
    },
    "ja": {
        "lang": "どの言語で話しますか？",
        "agent": "どのエージェントに接続しますか？",
        "name": "何とお呼びしましょうか？  (空欄なら名前を呼びません)",
        "name_hint": "毎回ではなく、ときどき呼びます。",
        "done": "完了。あとで変更するには:  crier lang · crier voice · crier name",
        "voice": "声はあとで `crier voices` で選んでください。今は F2 です。",
    },
}


def guess_lang() -> str:
    loc = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    for code, _ in LANGS:
        if loc.startswith(code):
            return code
    return "en"


def tty():
    """A human to talk to, or None. stdin is the install script — don't touch it."""
    try:
        return open("/dev/tty", "r+")
    except OSError:
        return None


def choose(term, question: str, options: list[tuple[str, str]], default: str) -> str:
    idx = next(i for i, (v, _) in enumerate(options) if v == default)
    print(f"\n  {question}", file=term)
    for i, (_, label) in enumerate(options, 1):
        mark = "→" if i == idx + 1 else " "
        print(f"   {mark} {i}) {label}", file=term)
    term.flush()

    while True:
        print(f"\n  [{idx + 1}] > ", end="", file=term)
        term.flush()
        answer = term.readline().strip()
        if not answer:
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1][0]
        print("   ?", file=term)


def ask_name(term, t: dict) -> str:
    print(f"\n  {t['name']}", file=term)
    print(f"   {t['name_hint']}", file=term)
    print("\n  > ", end="", file=term)
    term.flush()
    return term.readline().strip()


def main() -> int:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--lang")
    p.add_argument("--agent")
    p.add_argument("--name")
    p.add_argument("--voice")
    p.add_argument("--tone")
    p.add_argument("--yes", action="store_true")
    args, _ = p.parse_known_args()

    cfg = json.loads(CFG.read_text()) if CFG.exists() else \
        json.loads((ROOT / "config.default.json").read_text())

    lang = args.lang or cfg.get("lang") or guess_lang()
    agent = args.agent or "claude"
    name = args.name

    term = None if args.yes else tty()
    if term:
        # Everything the wizard says is in the language being chosen, so start with
        # the guess and re-read the strings the moment they pick.
        lang = choose(term, ASK[guess_lang()]["lang"], LANGS, lang)
        t = ASK[lang]
        agent = choose(term, t["agent"], AGENTS, agent)
        if name is None:
            name = ask_name(term, t)
        print(f"\n  {t['voice']}", file=term)
        print(f"  {t['done']}\n", file=term)
        term.close()
    else:
        # Nobody's there. Take what we were told, guess the rest, and be loud about it.
        t = ASK[lang]
        print(f"  no terminal — lang={lang}, agent={agent}"
              f"{f', name={name}' if name else ''}  (override with --lang/--agent/--name)")

    cfg["lang"] = lang
    if name is not None:
        cfg["call_name"] = name
    if args.voice:
        cfg["voice"] = args.voice
    if args.tone:
        cfg["tone"] = args.tone
    CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")

    # install.sh reads this to know which agent to wire.
    print(agent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
