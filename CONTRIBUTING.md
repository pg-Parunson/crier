# Contributing

Thanks for being here. crier is small on purpose, so this is short.

## The one rule

Every announcement crier makes has to pass a single test:

> **Does hearing this change what you do?**

"Task finished" passes — you come back. "Permission needed" passes — you approve or don't. "Starting work…" fails — you just pressed enter, nothing changes. That one is off by default, and no rewording will get it turned on, because the wording was never the problem.

If your PR adds something crier *says*, apply the test first. If your PR adds a feature, the same spirit applies: crier stays a small tool that speaks briefly and is otherwise silent. Sound packs, GUIs, dashboards and wake words are all lovely ideas for a different project.

## Running the tests

```bash
tests/run.sh
```

No network, no model download, a few seconds. CI runs exactly this on Ubuntu and macOS. If you change `locales.json`, the contract test will tell you what's missing.

The one thing tests can't cover is actual sound from an actual speaker. Before you open a PR that touches the audio path, run `crier demo` once and listen.

## Adding a language

All spoken text lives in [`locales.json`](locales.json). Copy the `en` block, translate, and keep the shape:

- `tone_hint` — five entries, `"1"` (deadpan) to `"5"` (goofball). These are instructions **to the agent**, in the target language, telling it how to write its spoken line. Level 5 should read like a real person from 2026, not a meme collection.
- `"1"`–`"5"` — canned lines for the contentless events (permission, idle, error, compact). Several variants each; one is picked at random so a line heard twenty times a day doesn't wear out.
- `errors` — the closed `error_type` enum. Every key, plus `_default`.
- `prompt` — the instruction block installed into the agent's memory file.
- `cli` — what crier says after you change a setting.

Two things outside `locales.json`:

- `detect()` in [`bin/announce.py`](bin/announce.py) picks the TTS language from the text itself (Hangul → ko, kana → ja, else en). If your language needs its own detection, add a branch.
- If your language reads numbers differently depending on the counter word (like Korean's 세 개 vs 삼 번), look at [`bin/korean.py`](bin/korean.py) — that's the pattern to follow, as its own file.

Check your language is in Supertonic's supported list first (`supertonic.SUPPORTED_LANGUAGES` — 31 languages).

## Adding an agent

[`bin/wire.py`](bin/wire.py) is a routing table, not a framework. An agent entry needs:

1. Which settings file to write hooks into, and the hook names it uses.
2. If its payload field names differ from Claude Code's, a rename in `normalize()` in `bin/announce.py`.
3. Where its user-level instruction file lives, in `bin/prompt.py` (`target()`), so the `[say]` line gets installed. If it has no such file (like Cursor), return `None` and the instruction is printed for manual pasting.

The bar: crier must get (a) turn-end with the assistant's text, and (b) permission requests with the tool being approved. An agent that only offers a contentless ping can't carry a spoken brief — that's peon-ping territory, and we point people there.

## PRs

- Small and focused beats large and complete.
- If it changes behavior someone might have depended on, say so in the PR body.
- I use this tool every day, so PRs get tried on a real machine before merging. That's the review.
