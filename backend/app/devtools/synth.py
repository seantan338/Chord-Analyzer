"""Deterministic song synthesizer for tests and local demos (not used in production flow).

Renders a chord progression with a plucked/keys-like timbre, a bass line and a simple
drum kit, so the full pipeline can be exercised without copyrighted recordings.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from app.music.chords import chord_pitch_classes, parse_chord

FloatArray = npt.NDArray[np.float32]


@dataclass(frozen=True)
class SongSection:
    chords: Sequence[str]  # one chord per bar
    timbre: str = "keys"  # "keys" or "pad" (changes structure features)
    drums: bool = True
    gain: float = 1.0


def _midi_to_hz(midi: float) -> float:
    return float(440.0 * 2.0 ** ((midi - 69) / 12))


def _tone(freq: float, n: int, sr: int, decay: float, n_harmonics: int = 6) -> FloatArray:
    t = np.arange(n) / sr
    wave = np.zeros(n, dtype=np.float64)
    for k in range(1, n_harmonics + 1):
        if freq * k > sr / 2.2:
            break
        wave += np.sin(2 * np.pi * freq * k * t) / k**1.3
    env = np.exp(-t / decay) * (1 - np.exp(-t / 0.004))
    return np.asarray(wave * env, dtype=np.float32)


def _kick(n: int, sr: int) -> FloatArray:
    t = np.arange(n) / sr
    freq = 50 + 70 * np.exp(-t / 0.03)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    return (np.sin(phase) * np.exp(-t / 0.12)).astype(np.float32)


def _noise_burst(n: int, sr: int, decay: float, rng: np.random.Generator, hp: bool) -> FloatArray:
    t = np.arange(n) / sr
    noise = rng.standard_normal(n)
    if hp:
        noise = np.diff(noise, prepend=0.0)
    return (noise * np.exp(-t / decay)).astype(np.float32)


def _chord_voicing(symbol: str) -> tuple[list[float], float]:
    chord = parse_chord(symbol)
    pcs = chord_pitch_classes(chord)
    base = 60  # around middle C
    notes = [base + ((pc - 0) % 12) for pc in pcs]
    notes = [n if n >= 57 else n + 12 for n in notes]  # keep voicing between A3 and G#5
    bass_pc = chord.bass if chord.bass is not None else chord.root
    bass_midi = 36 + (bass_pc % 12)  # C2..B2
    return [_midi_to_hz(n) for n in notes], _midi_to_hz(bass_midi)


def render_song(
    sections: Sequence[SongSection],
    bpm: float,
    beats_per_bar: int = 4,
    sr: int = 22050,
    lead_in_seconds: float = 0.0,
    seed: int = 7,
) -> FloatArray:
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    bar_len = beat * beats_per_bar
    n_bars = sum(len(s.chords) for s in sections)
    total = lead_in_seconds + n_bars * bar_len + 1.0
    out = np.zeros(int(total * sr) + sr, dtype=np.float32)

    def add(signal: FloatArray, start_s: float, gain: float) -> None:
        i = int(start_s * sr)
        j = min(len(out), i + len(signal))
        out[i:j] += gain * signal[: j - i]

    bar_index = 0
    for section in sections:
        for symbol in section.chords:
            bar_start = lead_in_seconds + bar_index * bar_len
            freqs, bass_hz = _chord_voicing(symbol)
            for b in range(beats_per_bar):
                t0 = bar_start + b * beat
                n = int(beat * sr * (1.0 if section.timbre == "keys" else 1.05))
                decay = 0.35 if section.timbre == "keys" else 1.5
                harmonics = 6 if section.timbre == "keys" else 3
                for f in freqs:
                    add(_tone(f, n, sr, decay, harmonics), t0, 0.16 * section.gain)
                add(_tone(bass_hz, n, sr, 0.5, 3), t0, 0.35 * section.gain)
                if section.drums:
                    if b % 2 == 0:
                        add(_kick(int(0.3 * sr), sr), t0, 0.55)
                    else:
                        add(_noise_burst(int(0.2 * sr), sr, 0.05, rng, hp=False), t0, 0.18)
                    for half in (0.0, 0.5):
                        add(
                            _noise_burst(int(0.06 * sr), sr, 0.012, rng, hp=True),
                            t0 + half * beat,
                            0.05,
                        )
            bar_index += 1

    out += 0.002 * rng.standard_normal(len(out)).astype(np.float32)
    peak = float(np.max(np.abs(out))) or 1.0
    return (0.9 * out / peak).astype(np.float32)


def simple_song(
    progression: Sequence[str], bpm: float, repeats: int = 4, beats_per_bar: int = 4
) -> FloatArray:
    return render_song([SongSection(chords=list(progression) * repeats)], bpm, beats_per_bar)
