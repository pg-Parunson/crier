#!/usr/bin/env python3
"""Speak status, not prose.

One entry point for every hook. It reads the hook JSON on stdin, decides whether
this event is worth interrupting a human for, turns it into a single short
sentence, and hands that to a detached child. The hook returns in ~50ms and never
writes to stdout, so it cannot influence the agent's control flow.

The premise: the full answer is already on screen, and reading beats listening.
Voice only earns its keep when you are NOT looking — it finished, it needs you,
it broke.

A chime plays first. That is a cushion (a voice out of nowhere makes you jump),
and it doubles as latency cover: the speech is synthesized while the chime rings,
so the words land as it fades.
"""

import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import korean

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text())
LOCALES = json.loads((ROOT / "locales.json").read_text())

L = LOCALES.get(CFG.get("lang", "en")) or LOCALES["en"]
TONE = L.get(CFG.get("tone", "plain")) or L["plain"]
EV = CFG["events"]

STATE = Path(tempfile.gettempdir()) / "agent-voice"
PLAY_PID = STATE / "play.pid"
LAST_SPOKE = STATE / "last"
EARCONS = ROOT / "assets" / "earcons"


def phrase(key: str, **kw) -> str:
    """A random variant for this event — a line you hear all day shouldn't repeat.

    Only the contentless events live in locales.json. The one announcement that
    carries real information — what just happened — is written by the agent itself
    (see summarize), because a sentence canned in a file cannot know that.
    """
    options = TONE.get(key) or L["plain"].get(key) or [""]
    return random.choice(options).format(**kw)


# --- the agent's reply -> one speakable line ---------------------------------

FENCE = re.compile(r"```.*?```", re.S)
MD_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
URL = re.compile(r"https?://\S+")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.M)
HRULE = re.compile(r"^\s*([-*_])\1{2,}\s*$", re.M)
HEADER = re.compile(r"^#{1,6}\s*", re.M)
BULLET = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+", re.M)
BACKTICK = re.compile(r"`([^`]*)`")
EMPHASIS = re.compile(r"(\*\*|__|\*|_|~~)")
INDENT_CODE = re.compile(r"^(?: {4}|\t).*$", re.M)
# "src/components/Button.tsx" is unlistenable; a person would just say "Button.tsx".
PATHISH = re.compile(r"(?<![\w/])(?:[\w.-]+/){1,}([\w.-]+)")
WS = re.compile(r"[ \t]+")


def prose(text: str) -> str:
    for pat in (FENCE, MD_IMG, URL, TABLE_ROW, HRULE, INDENT_CODE):
        text = pat.sub(" ", text)
    text = MD_LINK.sub(r"\1", text)
    text = HEADER.sub("", text)
    text = BULLET.sub("", text)
    text = BACKTICK.sub(r"\1", text)
    text = EMPHASIS.sub("", text)
    text = PATHISH.sub(r"\1", text)
    return WS.sub(" ", text)


SENTENCE = re.compile(r"[^.!?。？！\n]+[.!?。？！]?")


def summarize(reply: str) -> str:
    """Prefer the line the agent wrote to be spoken; else fall back to its own words."""
    marker = CFG["marker"]
    for line in reply.splitlines():
        s = line.strip()
        if s.startswith(marker):
            return prose(s[len(marker):]).strip()[: CFG["max_chars"]]

    # No marker — the prompt isn't installed, or the agent skipped it. Take the last
    # sentence if it's a question (that's what you have to answer), else the first,
    # which is where the outcome gets stated. The middle is detail you can read.
    lines = [s.strip() for s in SENTENCE.findall(prose(reply)) if s.strip()]
    if not lines:
        return ""
    pick = lines[-1] if lines[-1].endswith(("?", "？")) else lines[0]
    return pick[: CFG["max_chars"]]


# --- an event -> (chime, sentence) -------------------------------------------


def permission_line(tool: str, tool_input: dict) -> str:
    # Agents write a plain-language `description` alongside every shell command —
    # "Delete the build folder" next to `rm -rf build`. It is already there, already
    # written by the model, and free. Speaking it beats anything we could assemble:
    # a person asks "shall I delete the build folder?", not "shall I run rm?".
    said = (tool_input.get("description") or "").strip().rstrip(".")
    if said:
        return phrase("permission_described", what=said)

    # No description — reconstruct something. The verb carries the most meaning:
    # "rm" at least tells you what's at stake. "Bash needs approval" tells you nothing.
    if tool == "Bash":
        cmd = (tool_input.get("command") or "").strip()
        if cmd:
            return phrase("permission_bash", what=cmd.split()[0])
    if tool in ("Edit", "Write"):
        path = (tool_input.get("file_path") or "").strip()
        if path:
            return phrase("permission_file", what=Path(path).name)
    return phrase("permission_other", what=L["tools"].get(tool, tool))


def normalize(hook: dict) -> dict:
    """Translate a vendor's hook payload into the one shape we speak from.

    Claude Code and Codex CLI already agree — same event names, same fields — so
    they pass through untouched. Gemini and Cursor say the same things in different
    words, which makes this a rename table rather than four integrations.
    """
    if "hook_event_name" in hook:
        return hook  # Claude Code, Codex CLI

    # Gemini CLI — ~/.gemini/settings.json
    if "prompt_response" in hook:
        return {**hook, "hook_event_name": "Stop",
                "last_assistant_message": hook["prompt_response"]}

    # Cursor — ~/.cursor/hooks.json
    kind = hook.get("hook_event_name") or hook.get("event")
    if kind == "afterAgentResponse" or ("text" in hook and "loop_count" in hook):
        return {**hook, "hook_event_name": "Stop",
                "last_assistant_message": hook.get("text", "")}
    if "command" in hook and "cwd" in hook:  # Cursor beforeShellExecution
        return {**hook, "hook_event_name": "PermissionRequest",
                "tool_name": "Bash", "tool_input": {"command": hook["command"]}}
    if kind == "preToolUse":
        return {**hook, "hook_event_name": "PermissionRequest",
                "tool_name": hook.get("tool_name") or hook.get("toolName", ""),
                "tool_input": hook.get("tool_input") or hook.get("toolArgs") or {}}

    return hook


def line_for(raw: dict) -> tuple[str, str] | None:
    """(chime, sentence), or None to stay quiet."""
    hook = normalize(raw)
    ev = hook.get("hook_event_name")

    if ev == "Stop":
        if not EV["task_complete"]:
            return None
        said = summarize(hook.get("last_assistant_message") or "")
        return ("done", said) if said else None

    if ev == "StopFailure":
        if not EV["error"]:
            return None
        errs = L["errors"]
        return ("error", phrase("error", what=errs.get(hook.get("error_type", ""), errs["_default"])))

    if ev == "PermissionRequest":
        if not EV["permission"]:
            return None
        return ("ask", permission_line(hook.get("tool_name", ""), hook.get("tool_input") or {}))

    if ev == "Notification":
        kind = hook.get("notification_type")
        if kind == "idle_prompt" and EV["idle"]:
            return ("idle", phrase("idle"))
        if kind == "agent_needs_input" and EV["permission"]:
            return ("ask", phrase("agent_needs_input"))
        # permission_prompt is already covered by PermissionRequest — don't say it twice.
        return None

    if ev == "SubagentStart":
        # Fires once per agent, and a heavy turn keeps spawning them for minutes, so
        # a cooldown alone would only flatten the opening burst. Announce the turn's
        # first agent, then stay quiet until the next prompt.
        #
        # Off by default: hearing "starting work" right after you pressed enter
        # changes nothing you do. No wording fixes that — the event has no content.
        if not EV["agent_start"] or not first_in_turn("agent_start", hook):
            return None
        return ("start", phrase("agent_start"))

    if ev == "SubagentStop":
        if not EV["agent_done"]:
            return None
        return ("done", phrase("agent_done", what=hook.get("agent_type", "")))

    if ev == "PreCompact":
        if not EV["compact"] or hook.get("trigger") != "auto":
            return None
        return ("neutral", phrase("compact"))

    return None


def address(text: str) -> str:
    """Use their name sometimes. Every time grates; never is impersonal."""
    name = (CFG.get("call_name") or "").strip()
    if not name or random.random() >= CFG.get("name_chance", 0):
        return text
    return f"{name}, {text}"


# --- speaking -----------------------------------------------------------------


def first_in_turn(key: str, hook: dict) -> bool:
    """True only for the first such event of this turn, in this session.

    Keyed per session so ten parallel projects don't silence each other; the
    cooldown is what handles cross-session noise.
    """
    STATE.mkdir(parents=True, exist_ok=True)
    turn = f"{hook.get('session_id', '')}:{hook.get('prompt_id', '')}"
    if turn == ":":
        return True  # no turn identity to dedupe on — let the cooldown decide
    seen = STATE / f"turn-{key}-{hook.get('session_id', 'x')}"
    try:
        if seen.read_text() == turn:
            return False
    except OSError:
        pass
    seen.write_text(turn)
    return True


# Being told you're needed matters more than a tidy soundscape. These skip the
# cooldown: a chatty announcement must never swallow a permission prompt.
URGENT = {"ask", "error"}


def cooled_down(chime: str) -> bool:
    STATE.mkdir(parents=True, exist_ok=True)
    now = time.time()
    if chime in URGENT:
        LAST_SPOKE.write_text(str(now))
        return True
    try:
        if now - float(LAST_SPOKE.read_text()) < CFG["cooldown_sec"]:
            return False
    except (OSError, ValueError):
        pass
    LAST_SPOKE.write_text(str(now))
    return True


def detect(text: str) -> str:
    if re.search(r"[가-힣]", text):
        return "ko"
    if re.search(r"[぀-ヿ]", text):
        return "ja"
    return "en"


def synth(text: str, path: Path) -> bool:
    lang = detect(text)
    if lang == "ko":
        # Korean has two number systems and the engine picks the wrong one about half
        # the time — it read `3번` (item three) as 세 번 (three times). Spell every
        # number out in Hangul first so it never has to guess. See korean.py.
        text = korean.normalize(text)

    body = json.dumps({
        "text": text, "voice": CFG["voice"], "lang": lang,
        "speed": CFG["speed"], "steps": CFG["steps"], "response_format": "wav",
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{CFG['port']}/v1/tts",
        data=body, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            path.write_bytes(r.read())
        return path.stat().st_size > 44
    except (urllib.error.URLError, OSError, TimeoutError):
        return False  # daemon down — stay silent rather than break the turn


PLAYER = ["afplay"] if sys.platform == "darwin" else ["aplay", "-q"]


def play(path: Path) -> int:
    p = subprocess.Popen(PLAYER + [str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PLAY_PID.write_text(str(p.pid))
    return p.wait()


def perform(chime: str, text: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="av-", dir=STATE))
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            wav = tmp / "say.wav"
            pending = pool.submit(synth, text, wav)  # synthesize under the chime

            bell = EARCONS / f"{chime}.wav"
            if CFG["earcons"]["enabled"] and bell.exists():
                if play(bell) != 0:
                    return  # barged in before we even spoke
                time.sleep(CFG["earcons"]["gap_ms"] / 1000)

            if pending.result():
                play(wav)
    finally:
        PLAY_PID.unlink(missing_ok=True)
        subprocess.run(["rm", "-rf", str(tmp)], check=False)


def main() -> int:
    if os.environ.get("AGENT_VOICE_CHILD"):
        chime, _, text = sys.stdin.read().partition("\n")
        perform(chime.strip(), text.strip())
        return 0

    try:
        hook = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    try:
        got = line_for(hook)
    except Exception:
        return 0  # a broken announcement must never break the session

    if not got:
        return 0
    chime, text = got
    if not cooled_down(chime):
        return 0

    child = subprocess.Popen(
        [sys.executable, __file__],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, env={**os.environ, "AGENT_VOICE_CHILD": "1"},
    )
    child.stdin.write(f"{chime}\n{address(text)}".encode())
    child.stdin.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
