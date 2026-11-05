"""Tiny deterministic DSP toolkit used by gen_audio.py.

Everything here is plain numpy: no scipy, no external samples. Every generator
takes an explicit seed so a given build always produces byte-identical audio.
"""

from __future__ import annotations

import wave

import numpy as np

SR = 44100


def rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(np.uint64(seed) & np.uint64(0xFFFFFFFF))


def t_axis(dur: float, sr: int = SR) -> np.ndarray:
    return np.arange(int(dur * sr), dtype=np.float64) / sr


def sine(freq, dur: float, sr: int = SR, phase: float = 0.0) -> np.ndarray:
    t = t_axis(dur, sr)
    if np.isscalar(freq):
        return np.sin(2 * np.pi * freq * t + phase)
    return np.sin(2 * np.pi * np.cumsum(np.asarray(freq, dtype=np.float64)) / sr + phase)


def sweep(f0: float, f1: float, dur: float, sr: int = SR, curve: float = 1.0) -> np.ndarray:
    """Exponential pitch glide from f0 to f1 (curve>1 bends later)."""
    t = t_axis(dur, sr)
    n = t.size
    if n == 0:
        return t
    x = (t / max(dur, 1e-9)) ** curve
    freq = f0 * (f1 / f0) ** x
    return np.sin(2 * np.pi * np.cumsum(freq) / sr)


def saw(freq, dur: float, sr: int = SR) -> np.ndarray:
    t = t_axis(dur, sr)
    if not np.isscalar(freq):
        t = np.cumsum(np.asarray(freq, dtype=np.float64)) / sr
    return 2.0 * (t * freq % 1.0) - 1.0 if np.isscalar(freq) else 2.0 * (t % 1.0) - 1.0


def noise(dur: float, seed: int, sr: int = SR) -> np.ndarray:
    return rng(seed).uniform(-1.0, 1.0, int(dur * sr))


def adsr(n: int, a: float = 0.005, d: float = 0.08, s: float = 0.35, r: float = 0.15, sr: int = SR) -> np.ndarray:
    a_n, d_n, r_n = int(a * sr), int(d * sr), int(r * sr)
    s_n = max(n - a_n - d_n - r_n, 0)
    env = np.concatenate([
        np.linspace(0.0, 1.0, a_n, endpoint=False) if a_n else np.array([]),
        np.linspace(1.0, s, d_n, endpoint=False) if d_n else np.array([]),
        np.full(s_n, s),
        np.linspace(s, 0.0, r_n) if r_n else np.array([]),
    ])
    if env.size < n:
        env = np.pad(env, (0, n - env.size))
    return env[:n]


def exp_decay(dur: float, tau: float, sr: int = SR) -> np.ndarray:
    return np.exp(-t_axis(dur, sr) / max(tau, 1e-9))


def lowpass(x: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    """One-pole low-pass; cutoff may be a scalar or a per-sample array."""
    a = np.exp(-2.0 * np.pi * np.asarray(cutoff, dtype=np.float64) / sr)
    a = np.clip(a, 0.0, 0.9999)
    if a.ndim == 0:
        a = np.full(x.size, float(a))
    # Plain scalar loop, but over Python floats: roughly 8x faster than numpy
    # scalar indexing and keeps the module dependency-free.
    xs = np.asarray(x, dtype=np.float64).tolist()
    als = np.asarray(a, dtype=np.float64).tolist()
    y = [0.0] * len(xs)
    acc = 0.0
    for i in range(len(xs)):
        acc = (1.0 - als[i]) * xs[i] + als[i] * acc
        y[i] = acc
    return np.asarray(y, dtype=np.float64)


def highpass(x: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    return x - lowpass(x, cutoff, sr)


def bandpass(x: np.ndarray, lo: float, hi: float, sr: int = SR) -> np.ndarray:
    return lowpass(highpass(x, lo, sr), hi, sr)


def reverb(x: np.ndarray, wet: float = 0.25, decay: float = 0.35, seed: int = 7, sr: int = SR) -> np.ndarray:
    """Cheap Schroeder-ish tail: three combs plus a diffuse noise smear."""
    if wet <= 0:
        return x
    out = np.copy(x)
    for k, delay in enumerate((0.031, 0.047, 0.071)):
        d = int(delay * sr)
        if d >= x.size:
            continue
        g = decay ** (1 + k)
        tail = np.zeros_like(x)
        tail[d:] = x[:-d] * g
        out += tail * 0.6
    smear = np.convolve(x, exp_decay(0.12, 0.035, sr)[: int(0.12 * sr)], mode="full")[: x.size]
    out += smear * 0.15
    return x * (1.0 - wet) + out * wet


def saturate(x: np.ndarray, drive: float = 1.4) -> np.ndarray:
    return np.tanh(x * drive) / np.tanh(drive)


def normalize(x: np.ndarray, peak: float = 0.92) -> np.ndarray:
    m = float(np.max(np.abs(x))) if x.size else 0.0
    if m < 1e-9:
        return x
    return x * (peak / m)


def pad(x: np.ndarray, dur: float, sr: int = SR) -> np.ndarray:
    n = int(dur * sr)
    if x.size >= n:
        return x[:n]
    return np.pad(x, (0, n - x.size))


def declick(x: np.ndarray, ms: float = 3.0, sr: int = SR) -> np.ndarray:
    n = max(int(ms * 1e-3 * sr), 1)
    if x.size < 2 * n:
        return x
    ramp = np.linspace(0.0, 1.0, n)
    x = np.copy(x)
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x


def write_wav(path, x: np.ndarray, sr: int = SR, peak: float = 0.92) -> dict:
    y = declick(normalize(np.asarray(x, dtype=np.float64), peak), sr=sr)
    pcm = np.clip(y, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sr)
        fh.writeframes(pcm.tobytes())
    return {"path": str(path), "seconds": round(y.size / sr, 4), "bytes": pcm.nbytes}
