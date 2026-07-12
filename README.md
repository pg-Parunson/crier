# crier

**Your coding agent tells you what happened — out loud, in one sentence, only when it matters.**

Korean · English · Japanese. Runs entirely on your machine. No API key, no cloud, no per-character billing.

[한국어 README](README.ko.md)

```
🔔  "Fixed the memory leak, all three tests pass. Want me to commit?"
🔔  "May I run rm?"
🔔  "You've hit the rate limit."
```

Not a notification sound. A sentence you can act on without looking at the screen.

---

## Why

You alt-tab away while the agent works. Something dings. You come back — and now you have to read the screen anyway to find out what happened.

[peon-ping](https://github.com/PeonPing/peon-ping) proved the trigger model is right: hook the agent's lifecycle, make a noise. But a fixed sound can only tell you *something* happened, never *what*. So you still look.

crier puts a sentence where the sound was.

The rule for what gets spoken is one question: **does hearing this change what you do?**

| Event | Spoken | Changes what you do? |
|---|---|---|
| Turn finished | *"Fixed the memory leak, all three tests pass. Want me to commit?"* | ✅ come back and check |
| Permission needed | *"May I run `rm`?"* | ✅ approve or don't |
| Request failed | *"You've hit the rate limit."* | ✅ wait, or go do something else |
| Idle too long | *"Still here whenever you're ready."* | ✅ come back |
| ~~Subagent started~~ | ~~*"Starting work…"*~~ | ❌ **off by default** |

That last row is the whole design in miniature. You just pressed enter — being told "starting work" changes nothing. No amount of rewording fixes it, because the wording isn't the problem: **the event has no content.** So it stays off.

## Who writes the sentence

The agent does.

crier asks it to end each reply with one spoken line:

```
[say] Fixed the memory leak, all three tests pass. Want me to commit?
```

**There is no second API call and no second key.** The model that just did the work — the only thing in the system that knows what the turn was about — writes one more line. A handful of output tokens. If you're using a coding agent, you already have everything crier needs.

```bash
bin/voiced prompt install     # adds the instruction to your agent's memory file
```

Skip it and crier falls back to a rule: the last sentence if it's a question (that's what you have to answer), otherwise the first (that's where the outcome gets stated). It works, but the agent writes a better line than any rule can.

The contentless announcements — permission, error, idle — are canned in [`locales.json`](locales.json), because there's nothing for a model to add. It's already known what they say.

## Install

```bash
git clone https://github.com/pg-Parunson/crier
cd crier
./install.sh          # or: ./install.sh codex | gemini | cursor
```

Then restart your agent session.

Requires [uv](https://docs.astral.sh/uv/) and macOS. (Linux needs `aplay`; playback is untested — PRs welcome.)

## Agents

| Agent | Turn end + text | Permission + which command |
|---|---|---|
| **Claude Code** | ✅ | ✅ |
| **Codex CLI** | ✅ | ✅ |
| **Gemini CLI** | ✅ | ✅ |
| **Cursor** | ✅ | ✅ |

Claude Code and Codex use identical event names and payloads, so they share a hook. Gemini and Cursor say the same things in different words — [`announce.py`](bin/announce.py) normalizes them. Adding an agent is a routing-table entry in [`bin/wire.py`](bin/wire.py), not an integration.

Agents that only expose a contentless ping (Aider) can't carry a brief. crier is the wrong tool there; use peon-ping.

## The voice

[Supertonic](https://github.com/supertone-inc/supertonic) — a local ONNX model, no GPU, no network. 10 voices (F1–F5, M1–M5), 31 languages.

```bash
bin/voiced voices            # hear all ten
bin/voiced voice M3
bin/voiced lang ja           # ko | en | ja
bin/voiced tone playful      # plain | friendly | playful
bin/voiced name "Jaeho"      # used now and then, not every time
bin/voiced demo              # hear every event
```

**Korean actually works**, which is worth saying because most open TTS silently doesn't. Kokoro-82M has no Korean at all (its maintainer dropped it). Chatterbox Multilingual reports 70.9% CER on Korean — Resemble AI publishes that number themselves. Piper has no `ko_KR` voice. XTTS-v2 speaks Korean under a non-commercial license from a company that shut down in 2024, so it can never be relicensed. Supertonic is the one that reads `useEffect` as *"useEffect"* inside a Korean sentence instead of transliterating it into something unrecognizable.

Measured on an M-series Mac: RTF **0.159** — a 5-second sentence synthesizes in ~0.8s. (Supertonic's marketing claims 0.012. That did not reproduce here.) It's fast enough because of how the chime works, below.

## Tone

| | Permission | Idle |
|---|---|---|
| `plain` | *"May I run rm?"* | *"Waiting."* |
| `friendly` | *"Mind if I run rm?"* | *"Still here whenever you're ready."* |
| `playful` | *"rm. Shall we? I take no responsibility."* | *"Bored. Got anything?"* |

The tone goes into the canned lines **and** into the instruction the agent gets, so it carries through to the sentences the agent writes. A persona costs nothing here — it's a line in a prompt, not a model.

## Chimes

A voice arriving out of nowhere makes you jump, so a bell rings first.

The chimes are **synthesized at install** ([`bin/earcons.py`](bin/earcons.py)), never shipped as files — nothing to license, nothing to attribute. Each is a few harmonic partials under an exponential decay: a struck bell. **Rising** asks or announces; **falling** settles or warns. All under half a second.

They pay for themselves twice: **the speech is synthesized while the chime rings**, so the words land as it fades and you never hear the model think.

## Noise control

This is the part that decides whether you keep it installed.

A parallel fan-out fires a hook *per agent*. Run ten projects at once and a naive implementation becomes an attack.

1. **Once per turn.** Subagent announcements fire only for the turn's first agent (keyed on `prompt_id`). Eight agents or thirty, you hear it once — then silence until your next prompt. (A cooldown alone can't do this: a heavy turn keeps spawning agents for minutes, so it would only flatten the opening burst.)
2. **Cooldown** (2.5s, shared across sessions) so ten projects don't talk over each other.
3. **Priority.** Permission requests and errors **skip the cooldown.** A chatty announcement must never swallow *"May I run rm?"*.

Still too much? Every event has an off switch in `config.json`.

## Barge-in

Start typing and whatever it's saying stops mid-word.

## Why hooks, not MCP

- **A hook needs no cooperation from the model.** An MCP tool only runs if the model *decides* to call it — so the moment it thinks "task's done," your voice loop dies silently.
- Hooks live in the agent's settings file, which the **terminal and the IDE extension share.** VS Code's Claude extension can't even discover MCP servers.
- The hook returns in ~50ms and hands playback to a detached child. Your turn never waits for a sentence to finish.
- It writes nothing to stdout, so it **cannot influence the agent's control flow.** If crier breaks, your session doesn't.

## Config

`config.json` — re-read on every event, so changes apply immediately.

| | |
|---|---|
| `lang` `tone` `voice` `call_name` `name_chance` | who it is |
| `events.*` | what it speaks |
| `cooldown_sec` `max_chars` | how much |
| `earcons.enabled` `gap_ms` | the bell |
| `marker` | the prefix the agent writes its spoken line behind |

## License

MIT.

Supertonic's **code** is MIT; its **model weights are OpenRAIL-M**, which carries use restrictions. crier never vendors them — they're downloaded to your cache on first run, so that license lands on you directly rather than riding in on a clone.
