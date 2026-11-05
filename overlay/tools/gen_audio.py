"""Procedural sound-effect bank for Bubble Night: Nebula.

Every cue is synthesised from oscillators and filtered noise, so the repository
ships no third-party audio and the whole bank rebuilds in a couple of seconds.
Output: app/src/main/res/raw/<cue>.wav  (mono, 44.1 kHz, 16-bit PCM)

Run:  python3 tools/gen_audio.py [--out DIR] [--sr 44100]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

import dsp
from dsp import (
    SR, adsr, bandpass, exp_decay, highpass, lowpass, noise, normalize,
    pad, reverb, rng, saturate, sine, sweep, write_wav,
)

# --------------------------------------------------------------------------- #
# Individual cues
# --------------------------------------------------------------------------- #


def cue_launch() -> np.ndarray:
    """Cannon: a short rubbery thump plus a rising air swish."""
    d = 0.24
    body = sweep(520, 190, d, curve=0.6) * exp_decay(d, 0.055)
    click = bandpass(noise(d, 11), 900, 5200) * exp_decay(d, 0.018) * 0.55
    air = bandpass(noise(d, 12), 1800, 9000) * np.linspace(0, 1, int(d * SR)) ** 2 * 0.25
    return body * 0.9 + click + air


def cue_bounce() -> np.ndarray:
    """Wall bounce: dry, woody, very short."""
    d = 0.11
    tone = sine(760, d) * exp_decay(d, 0.022)
    tick = bandpass(noise(d, 21), 1400, 7000) * exp_decay(d, 0.010) * 0.6
    return saturate(tone * 0.8 + tick, 1.1)


def cue_pop(step: int = 0) -> np.ndarray:
    """Bubble pop. Each chain step raises the pitch, which is what makes a
    chain read as "going up" instead of repeating the same click."""
    d = 0.15
    f = 300 * (2 ** (step / 5.0))
    thump = sweep(f * 2.4, f, d, curve=0.5) * exp_decay(d, 0.030)
    snap = bandpass(noise(d, 31 + step), 700, 6000) * exp_decay(d, 0.012) * 0.8
    ring = sine(f * 3.1, d) * exp_decay(d, 0.055) * 0.22
    return saturate(thump + snap + ring, 1.25)


def cue_match() -> np.ndarray:
    """Three-in-a-row confirmation: a soft two-note chime."""
    d = 0.34
    out = np.zeros(int(d * SR))
    for i, f in enumerate((880.0, 1320.0)):
        seg = sine(f, 0.26) * exp_decay(0.26, 0.09) * 0.5
        at = int(i * 0.055 * SR)
        out[at:at + seg.size] += seg[: max(out.size - at, 0)]
    return reverb(out, wet=0.18)


def cue_chain(level: int = 1) -> np.ndarray:
    """Combo streak sting: a bright rising arpeggio, one semitone higher per level."""
    d = 0.42
    base = 523.25 * (2 ** ((level - 1) / 12.0))
    out = np.zeros(int(d * SR))
    for i, ratio in enumerate((1.0, 1.25, 1.5)):
        seg = sine(base * ratio, 0.16) * exp_decay(0.16, 0.045) * (1.0 - 0.18 * i)
        start = int(i * 0.075 * SR)
        out[start:start + seg.size] += seg[: max(out.size - start, 0)]
    return reverb(out, wet=0.22, seed=level)


def cue_drop() -> np.ndarray:
    """A whole cluster falling: descending whoosh with a low thud landing."""
    d = 0.40
    fall = sweep(900, 180, d, curve=1.6) * exp_decay(d, 0.14) * 0.7
    air = bandpass(noise(d, 41), 400, 3000) * exp_decay(d, 0.10) * 0.45
    thud = np.zeros(int(d * SR))
    land = sine(90, 0.16) * exp_decay(0.16, 0.05)
    at = int(0.26 * SR)
    thud[at:at + land.size] += land[: max(thud.size - at, 0)] * 1.1
    return reverb(fall + air + thud, wet=0.15)


def cue_star() -> np.ndarray:
    """Collecting a star: glassy bell with a shimmer tail."""
    d = 0.62
    out = np.zeros(int(d * SR))
    for i, f in enumerate((1318.5, 1760.0, 2637.0)):
        seg = sine(f, d) * exp_decay(d, 0.16 - i * 0.03) * (0.5 - i * 0.1)
        out += seg
    return reverb(out, wet=0.35, decay=0.4)


def cue_coin() -> np.ndarray:
    """Two quick metallic blips, the classic reward read."""
    d = 0.34
    out = np.zeros(int(d * SR))
    for i, f in enumerate((988.0, 1318.5)):
        seg = (sine(f, 0.18) * 0.6 + sine(f * 2.0, 0.18) * 0.25) * exp_decay(0.18, 0.055)
        at = int(i * 0.07 * SR)
        out[at:at + seg.size] += seg[: max(out.size - at, 0)]
    return out


def cue_fireball() -> np.ndarray:
    """Ignition then a rolling flame wash."""
    d = 0.62
    ignite = bandpass(noise(d, 51), 300, 4000) * np.linspace(0, 1, int(d * SR)) ** 1.6
    body = sweep(140, 70, d) * exp_decay(d, 0.22) * 0.6
    crackle = highpass(noise(d, 52), 5000) * (rng(53).random(int(d * SR)) > 0.995) * 2.4
    return saturate(reverb(ignite + body + crackle, wet=0.2), 1.5)


def cue_bomb() -> np.ndarray:
    """Explosion: sub drop, noise blast, long tail."""
    d = 1.05
    t = dsp.t_axis(d)
    sub = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-t * 3.2) + 28) / SR) * np.exp(-t * 2.6)
    blast = lowpass(noise(d, 61), np.maximum(9000 * np.exp(-t * 4.0), 120)) * np.exp(-t * 3.4)
    debris = bandpass(noise(d, 62), 200, 1400) * np.exp(-t * 1.4) * 0.4
    return saturate(reverb(sub * 1.1 + blast * 1.0 + debris, wet=0.32, decay=0.45), 1.3)


def cue_rocket() -> np.ndarray:
    """Launch whoosh with a doppler pass-by."""
    d = 0.70
    t = dsp.t_axis(d)
    whoosh = bandpass(noise(d, 71), 500, 2500 + 3500 * np.sin(np.pi * t / d)) * np.sin(np.pi * t / d) ** 1.2
    tone = sweep(220, 880, d, curve=0.7) * exp_decay(d, 0.28) * 0.35
    return reverb(whoosh + tone, wet=0.2)


def cue_lightning() -> np.ndarray:
    """Electric zap: fast FM crack plus buzz decay."""
    d = 0.55
    t = dsp.t_axis(d)
    buzz = np.sin(2 * np.pi * 110 * t + 6.0 * np.sin(2 * np.pi * 55 * t) * np.exp(-t * 9)) * np.exp(-t * 4.5)
    crack = highpass(noise(d, 81), 4000) * np.exp(-t * 22) * 1.2
    return saturate(reverb(buzz + crack, wet=0.25), 1.6)


def cue_freeze() -> np.ndarray:
    """Ice: crystalline high sparkle, slow attack."""
    d = 0.85
    t = dsp.t_axis(d)
    glass = np.zeros(int(d * SR))
    r = rng(91)
    for f in (1568.0, 2093.0, 3136.0, 4186.0):
        glass += np.sin(2 * np.pi * f * t + r.uniform(0, 6.28)) * np.exp(-t * 2.2) * 0.25
    air = bandpass(noise(d, 92), 3000, 11000) * np.minimum(t / 0.15, 1.0) * np.exp(-t * 1.6) * 0.3
    return reverb(glass + air, wet=0.4, decay=0.5)


def cue_shield() -> np.ndarray:
    """Bubble shield forming: swelling low hum with a metallic shimmer."""
    d = 0.60
    t = dsp.t_axis(d)
    hum = np.sin(2 * np.pi * 180 * t) * np.minimum(t / 0.1, 1.0) * np.exp(-t * 2.0) * 0.5
    shimmer = sine(1440, d) * np.sin(np.pi * t / d) * 0.3
    return reverb(hum + shimmer, wet=0.3)


def cue_rainbow() -> np.ndarray:
    """Wildcard bubble: ascending rainbow run."""
    d = 0.95
    out = np.zeros(int(d * SR))
    scale = (523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.66, 1318.5)
    for i, f in enumerate(scale):
        seg = (sine(f, 0.20) * 0.45 + sine(f * 2, 0.20) * 0.12) * exp_decay(0.20, 0.07)
        at = int(i * 0.062 * SR)
        out[at:at + seg.size] += seg[: max(out.size - at, 0)]
    return reverb(out, wet=0.3)


def cue_booster() -> np.ndarray:
    """Booster armed: two-note "ready" cue."""
    d = 0.52
    out = np.zeros(int(d * SR))
    for i, f in enumerate((659.25, 987.77)):
        seg = sine(f, 0.26) * exp_decay(0.26, 0.08) * 0.55
        at = int(i * 0.09 * SR)
        out[at:at + seg.size] += seg[: max(out.size - at, 0)]
    return reverb(out, wet=0.2)


def cue_daily() -> np.ndarray:
    """Daily reward fanfare: four-note major arpeggio over a pad."""
    d = 1.85
    out = np.zeros(int(d * SR))
    for i, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
        seg = (sine(f, 0.75) * 0.4 + sine(f * 2.01, 0.75) * 0.1) * exp_decay(0.75, 0.30)
        at = int(i * 0.14 * SR)
        out[at:at + seg.size] += seg[: max(out.size - at, 0)]
    pad_tone = (sine(261.63, d) * 0.10 + sine(392.0, d) * 0.08) * adsr(out.size, 0.25, 0.4, 0.5, 0.5)
    return reverb(out + pad_tone, wet=0.35, decay=0.5)


def cue_levelup() -> np.ndarray:
    d = 1.25
    out = np.zeros(int(d * SR))
    for i, f in enumerate((392.0, 523.25, 659.25, 783.99, 1046.5)):
        seg = sine(f, 0.55) * exp_decay(0.55, 0.22) * 0.42
        at = int(i * 0.105 * SR)
        out[at:at + seg.size] += seg[: max(out.size - at, 0)]
    return reverb(out, wet=0.32, decay=0.45)


def cue_victory() -> np.ndarray:
    """Level cleared: warm major cadence, 1.6 s."""
    d = 1.60
    out = np.zeros(int(d * SR))
    for i, (f, at) in enumerate(((523.25, 0.0), (659.25, 0.10), (783.99, 0.20), (1046.5, 0.32))):
        seg = (sine(f, 1.2) * 0.34 + sine(f * 1.5, 1.2) * 0.10) * exp_decay(1.2, 0.45)
        s = int(at * SR)
        out[s:s + seg.size] += seg[: max(out.size - s, 0)]
    bed = (sine(130.81, d) * 0.16 + sine(196.0, d) * 0.12) * adsr(out.size, 0.3, 0.3, 0.6, 0.6)
    return reverb(out + bed, wet=0.38, decay=0.5)


def cue_defeat() -> np.ndarray:
    """Out of shots: falling minor third, soft and never harsh."""
    d = 1.35
    out = np.zeros(int(d * SR))
    for i, f in enumerate((392.0, 349.23, 261.63)):
        seg = (sine(f, 0.8) * 0.35 + sine(f * 0.5, 0.8) * 0.15) * exp_decay(0.8, 0.35)
        s = int(i * 0.22 * SR)
        out[s:s + seg.size] += seg[: max(out.size - s, 0)]
    return reverb(lowpass(out, 3200), wet=0.3)


def cue_ui_tap() -> np.ndarray:
    d = 0.075
    return bandpass(noise(d, 101), 1200, 6000) * exp_decay(d, 0.012) * 0.7 + sine(1200, d) * exp_decay(d, 0.015) * 0.3


def cue_whoosh() -> np.ndarray:
    d = 0.42
    t = dsp.t_axis(d)
    return bandpass(noise(d, 111), 300, 2200 + 2600 * np.sin(np.pi * t / d)) * np.sin(np.pi * t / d) ** 1.5


def cue_aim() -> np.ndarray:
    """Aim guide tick, quiet and high so it can repeat every frame."""
    d = 0.06
    return sine(2400, d) * exp_decay(d, 0.010) * 0.35


CUES = {
    "launch": cue_launch,
    "bounce": cue_bounce,
    "match": cue_match,
    "drop": cue_drop,
    "victory": cue_victory,
    "defeat": cue_defeat,
    "pop1": lambda: cue_pop(0),
    "pop2": lambda: cue_pop(1),
    "pop3": lambda: cue_pop(2),
    "pop4": lambda: cue_pop(3),
    "pop5": lambda: cue_pop(4),
    "chain1": lambda: cue_chain(1),
    "chain2": lambda: cue_chain(2),
    "chain3": lambda: cue_chain(3),
    "star": cue_star,
    "coin": cue_coin,
    "fireball": cue_fireball,
    "bomb": cue_bomb,
    "rocket": cue_rocket,
    "lightning": cue_lightning,
    "freeze": cue_freeze,
    "shield": cue_shield,
    "rainbow": cue_rainbow,
    "booster": cue_booster,
    "daily": cue_daily,
    "levelup": cue_levelup,
    "ui_tap": cue_ui_tap,
    "whoosh": cue_whoosh,
    "aim": cue_aim,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="app/src/main/res/raw")
    ap.add_argument("--manifest", default="app/src/main/assets/nebula/audio_manifest.json")
    ap.add_argument("--sr", type=int, default=SR)
    ap.add_argument("--only", default="", help="comma separated cue names")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    wanted = {c.strip() for c in args.only.split(",") if c.strip()} or set(CUES)

    started = time.time()
    manifest = {}
    for name in sorted(CUES):
        if name not in wanted:
            continue
        info = write_wav(out / f"{name}.wav", CUES[name](), sr=args.sr)
        manifest[name] = {"file": f"{name}.wav", "seconds": info["seconds"], "bytes": info["bytes"]}
        print(f"  {name:<10} {info['seconds']:>5.2f}s  {info['bytes'] / 1024:>6.1f} KiB")

    mp = Path(args.manifest)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps({"sampleRate": args.sr, "cues": manifest}, indent=2, sort_keys=True) + "\n")
    total = sum(v["bytes"] for v in manifest.values())
    print(f"\n{len(manifest)} cues, {total / 1024:.0f} KiB, {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
