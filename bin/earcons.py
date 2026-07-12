#!/usr/bin/env python3
"""Generate the cushion chimes.

Synthesized here rather than shipped as audio files: no bundled assets, no
sample licensing to worry about when this gets published.

Each earcon is a struck-bell tone — a few harmonically related partials under an
exponential decay. Two notes carry a direction: rising asks or announces, falling
settles or warns. They are deliberately quiet and under half a second; this is a
doorbell before someone speaks, not an alarm.
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
ASSETS = Path(__file__).resolve().parent.parent / "assets" / "earcons"

# Equal temperament, A4 = 440
A5, C6, D6, E6, G5, G6, E5, C5, F5, A4, F4 = (
    880, 1046.5, 1174.7, 1318.5, 784.0, 1568.0, 659.3, 523.3, 698.5, 440.0, 349.2
)


def strike(freq: float, dur: float, decay: float = 7.0, amp: float = 1.0) -> np.ndarray:
    """One bell partial stack with a soft attack so it doesn't click."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    env = np.exp(-decay * t)
    attack = np.minimum(t / 0.004, 1.0)  # 4ms fade-in kills the transient click
    tone = (
        np.sin(2 * np.pi * freq * t)
        + 0.34 * np.sin(2 * np.pi * freq * 2.0 * t)
        + 0.12 * np.sin(2 * np.pi * freq * 3.01 * t)  # slightly inharmonic = bell-like
    )
    return tone * env * attack * amp


def seq(notes: list[tuple[float, float]], dur: float = 0.42, decay: float = 7.0,
        amp: float = 0.22) -> np.ndarray:
    """notes = [(freq, start_seconds)] — overlapping strikes, they ring into each other."""
    last = max(s for _, s in notes)
    out = np.zeros(int(SR * (dur + last)) + 16)  # slack: per-note rounding accumulates
    for freq, start in notes:
        i = int(SR * start)
        v = strike(freq, dur, decay)
        out[i:i + len(v)] += v
    peak = np.abs(out).max()
    return (out / peak * amp) if peak else out


EARCONS = {
    # Finished. Rising fourth, long ring — the sound of something resolving.
    "done":    seq([(G5, 0.0), (C6, 0.11), (E6, 0.19)], dur=0.55, decay=5.5),
    # Needs you. Rising second, short — a question, not a demand.
    "ask":     seq([(A5, 0.0), (D6, 0.10)], dur=0.38, decay=8.0),
    # Something broke. Falling, darker, slower decay.
    "error":   seq([(F5, 0.0), (A4, 0.10), (F4, 0.18)], dur=0.5, decay=6.0, amp=0.20),
    # Work starting. One light blip, gets out of the way.
    "start":   seq([(E6, 0.0), (G6, 0.06)], dur=0.22, decay=14.0, amp=0.16),
    # Idle. Low, soft, easy to ignore.
    "idle":    seq([(C5, 0.0)], dur=0.45, decay=7.0, amp=0.15),
    # Housekeeping. Neutral single tone.
    "neutral": seq([(E5, 0.0)], dur=0.35, decay=9.0, amp=0.15),
}


def build(force: bool = False) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, wav in EARCONS.items():
        path = ASSETS / f"{name}.wav"
        if force or not path.exists():
            sf.write(path, wav.astype(np.float32), SR)


if __name__ == "__main__":
    build(force="--force" in sys.argv)
    print(f"{len(EARCONS)}개 생성: {ASSETS}")
    if "--play" in sys.argv:
        import subprocess, time
        for name in EARCONS:
            print(f"  ♪ {name}")
            subprocess.run(["afplay", str(ASSETS / f"{name}.wav")])
            time.sleep(0.25)
