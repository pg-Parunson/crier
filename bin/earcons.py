#!/usr/bin/env python3
"""Generate the cushion chimes.

Synthesized here rather than shipped as audio files: no bundled assets, no sample
licensing to worry about when this gets published.

Two things make a chime hurt, and the first version had both. It sat around
C6–G6, so its second harmonic landed near 3 kHz — exactly where hearing is most
sensitive. And it had a 4 ms attack, which the ear reads as a click before it
reads as a tone.

So `soft` (the default) drops an octave into the 350–660 Hz range, fades in over
25 ms so the note arrives rather than hits, and drops the slightly-detuned partial
that gave the old one its metallic edge. What's left is close to a sine with a
little warmth on top — a doorbell in another room, not an alarm.

`bell` keeps the original if you like the brightness.

    earcons.py [--style soft|bell] [--force] [--play]
"""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "earcons"

# Two octaves lower than the bright set. Laptop speakers roll off below ~300 Hz,
# so this is about as warm as it can get and still be heard across a room.
F4, G4, A4, C5, D5, E5, F5, G5 = 349.2, 392.0, 440.0, 523.3, 587.3, 659.3, 698.5, 784.0
A5, C6, D6, E6, G6 = 880.0, 1046.5, 1174.7, 1318.5, 1568.0


def strike(freq: float, dur: float, decay: float, attack: float,
           partials: list[tuple[float, float]]) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    env = np.exp(-decay * t)
    env *= np.minimum(t / attack, 1.0)                    # ease in — no click
    env *= np.minimum((dur - t) / 0.03, 1.0).clip(0, 1)   # ease out — no cutoff pop
    tone = sum(amp * np.sin(2 * np.pi * freq * mult * t) for mult, amp in partials)
    return tone * env


def seq(notes, dur, decay, amp, attack, partials) -> np.ndarray:
    last = max(s for _, s in notes)
    out = np.zeros(int(SR * (dur + last)) + 16)  # slack: per-note rounding accumulates
    for freq, start in notes:
        i = int(SR * start)
        v = strike(freq, dur, decay, attack, partials)
        out[i:i + len(v)] += v
    peak = np.abs(out).max()
    return (out / peak * amp) if peak else out


# Nearly a sine. The tiny octave partial keeps it from sounding dead; there is no
# inharmonic partial at all, because that is what makes a bell sound like metal.
SOFT = dict(attack=0.025, partials=[(1.0, 1.0), (2.0, 0.12)])
BELL = dict(attack=0.004, partials=[(1.0, 1.0), (2.0, 0.34), (3.01, 0.12)])

STYLES = {
    "soft": {
        # Rising, low, unhurried — the sound of something settling into place.
        "done":    dict(notes=[(F4, 0.0), (A4, 0.13), (C5, 0.24)], dur=0.9, decay=3.2, amp=0.17),
        # A question. Rises, then stops before it resolves.
        "ask":     dict(notes=[(A4, 0.0), (D5, 0.12)], dur=0.7, decay=4.0, amp=0.17),
        # Falls. Darker, slower, but never a buzzer.
        "error":   dict(notes=[(F5, 0.0), (C5, 0.12), (A4, 0.22)], dur=0.85, decay=3.6, amp=0.16),
        # Gets out of the way immediately.
        "start":   dict(notes=[(C5, 0.0), (E5, 0.07)], dur=0.4, decay=7.0, amp=0.12),
        # Low and easy to ignore, which is the point.
        "idle":    dict(notes=[(G4, 0.0)], dur=0.8, decay=3.5, amp=0.11),
        "neutral": dict(notes=[(C5, 0.0)], dur=0.6, decay=5.0, amp=0.11),
    },
    "bell": {
        "done":    dict(notes=[(G5, 0.0), (C6, 0.11), (E6, 0.19)], dur=0.55, decay=5.5, amp=0.22),
        "ask":     dict(notes=[(A5, 0.0), (D6, 0.10)], dur=0.38, decay=8.0, amp=0.22),
        "error":   dict(notes=[(F5, 0.0), (A4, 0.10), (F4, 0.18)], dur=0.5, decay=6.0, amp=0.20),
        "start":   dict(notes=[(E6, 0.0), (G6, 0.06)], dur=0.22, decay=14.0, amp=0.16),
        "idle":    dict(notes=[(C5, 0.0)], dur=0.45, decay=7.0, amp=0.15),
        "neutral": dict(notes=[(E5, 0.0)], dur=0.35, decay=9.0, amp=0.15),
    },
}


def style_of() -> str:
    try:
        cfg = json.loads((ROOT / "config.json").read_text())
        return cfg.get("earcons", {}).get("style", "soft")
    except (OSError, json.JSONDecodeError):
        return "soft"


def build(style: str, force: bool = False) -> None:
    voice = SOFT if style == "soft" else BELL
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, spec in STYLES[style].items():
        path = ASSETS / f"{name}.wav"
        if force or not path.exists():
            sf.write(path, seq(**spec, **voice).astype(np.float32), SR)


if __name__ == "__main__":
    style = sys.argv[sys.argv.index("--style") + 1] if "--style" in sys.argv else style_of()
    if style not in STYLES:
        sys.exit(f"style must be one of: {', '.join(STYLES)}")

    build(style, force="--force" in sys.argv or "--style" in sys.argv)
    print(f"{len(STYLES[style])} chimes ({style}) → {ASSETS}")

    if "--play" in sys.argv:
        import subprocess, time
        for name in STYLES[style]:
            print(f"  ♪ {name}")
            subprocess.run(["afplay", str(ASSETS / f"{name}.wav")])
            time.sleep(0.35)
