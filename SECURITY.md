# Security

## What crier can see, and where it goes

The `Stop` hook receives the assistant's full reply text — that is how the spoken
line works. Here is exactly what happens to it:

- It is sent as JSON to a TTS server on **127.0.0.1** (a local Supertonic process
  crier starts). It never leaves your machine.
- Text is always passed as data — subprocess argument vectors and JSON bodies,
  never interpolated into a shell string.
- crier makes **no network calls at runtime**. The only downloads are at install
  time: the pinned `supertonic` package from PyPI, and the voice model from
  Hugging Face on first run (cached under `~/.cache/supertonic3`).
- There is no telemetry, no analytics, no phone-home of any kind. Grep the source;
  it's small.

## What crier modifies on your machine

Install writes to, and `crier uninstall` restores or removes:

- your agent's settings file (hooks) — **merged**, never replacing entries owned
  by other tools, with a timestamped backup taken first
- your agent's user-level memory file (the `[say]` instruction, in a fenced block)
- `~/.local/bin/crier` (symlink) and `~/.crier` (the clone itself)

## The `curl | sh` install

If piping to shell isn't acceptable in your environment, do it in two steps and
read it first — the script is short:

```bash
curl -fsSLO https://raw.githubusercontent.com/pg-Parunson/crier/main/bootstrap.sh
less bootstrap.sh
sh bootstrap.sh
```

## Reporting

Open a GitHub issue. If it's sensitive, email the address on the maintainer's
GitHub profile instead.
