"""End-to-end DSP checks on synthesized songs with known ground truth."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.pipeline import PipelineOptions, analyze_signal
from app.audio.types import AudioSignal
from app.devtools.synth import SongSection, render_song
from app.music.chords import Chord
from app.music.keys import Key, Mode

pytestmark = pytest.mark.slow
SR = 22050


def _chord_at(output: object, t: float) -> str:
    for c in output.chords:  # type: ignore[attr-defined]
        if c.start <= t < c.end:
            return "N" if c.root is None else Chord(c.root, c.suffix).format()
    return "?"


def _bar_accuracy(
    output: object, progression: list[str], bpm: float, bpb: int, lead: float
) -> float:
    bar = 60.0 / bpm * bpb
    hits = [
        _chord_at(output, lead + i * bar + bar / 2) == chord for i, chord in enumerate(progression)
    ]
    return float(np.mean(hits))


@pytest.mark.parametrize(
    ("progression", "bpm", "bpb", "key"),
    [
        (["C", "G", "Am", "F"], 100, 4, "C Major"),
        (["Am", "Dm", "E", "Am"], 76, 4, "A Minor"),
        (["D", "G", "A", "D"], 140, 3, "D Major"),
        (["Eb", "Bb", "Cm", "Ab"], 120, 4, "Eb Major"),
    ],
)
def test_synthetic_song(progression: list[str], bpm: float, bpb: int, key: str) -> None:
    lead = 0.6
    chords = progression * 4
    samples = render_song([SongSection(chords)], bpm, bpb, lead_in_seconds=lead)
    output = analyze_signal(AudioSignal(samples, SR), PipelineOptions())

    assert abs(output.tempo.bpm - bpm) / bpm < 0.02
    assert output.meter.beats_per_bar == bpb
    assert Key(output.key.tonic, Mode(output.key.mode)).name == key
    assert _bar_accuracy(output, chords, bpm, bpb, lead) >= 0.9
    assert output.chords[0].root is None  # silent lead-in is "no chord"
    assert all(0.0 <= c.confidence <= 1.0 for c in output.chords)


@pytest.mark.parametrize("bpm", [82, 164])
def test_tempo_octave_handling(bpm: float) -> None:
    """Never report the slow 41-BPM reading; offer the half/double reading as alternative."""
    samples = render_song([SongSection(["G", "C", "D", "G"] * 6)], bpm, 4)
    output = analyze_signal(AudioSignal(samples, SR), PipelineOptions())
    readings = [output.tempo.bpm, *output.tempo.alternatives]
    assert 60 <= output.tempo.bpm <= 180
    assert any(abs(r - bpm) / bpm < 0.02 for r in readings)
