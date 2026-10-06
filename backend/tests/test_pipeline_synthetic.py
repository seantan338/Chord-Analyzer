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
            return "N" if c.root is None else Chord(c.root, c.suffix, c.bass).format()
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


@pytest.mark.parametrize(
    "progression",
    [
        ["Cmaj7", "Am7", "Dm7", "G7"],
        ["C", "G/B", "Am", "F"],
        ["G", "D/F#", "Em", "C"],
        ["Eb", "Bb/D", "Cm7", "Ab"],
        ["Dsus4", "D", "Asus2", "A"],
        ["Bdim", "C", "Em", "Am"],
    ],
)
def test_extended_chords(progression: list[str]) -> None:
    samples = render_song([SongSection(progression * 3)], 100, 4, lead_in_seconds=0.5)
    output = analyze_signal(AudioSignal(samples, SR), PipelineOptions(chord_vocabulary="extended"))
    assert _bar_accuracy(output, progression * 3, 100, 4, 0.5) >= 0.9


def test_majmin_vocabulary_never_extends() -> None:
    samples = render_song([SongSection(["Cmaj7", "G/B", "Am7", "F"] * 3)], 100, 4)
    output = analyze_signal(AudioSignal(samples, SR), PipelineOptions(chord_vocabulary="majmin"))
    assert {c.suffix for c in output.chords} <= {"", "m", "N"}
    assert all(c.bass is None for c in output.chords)


def test_plain_triads_are_not_over_extended() -> None:
    samples = render_song(
        [SongSection(["C", "F", "G", "Am", "Em", "Dm", "G", "C"] * 2, timbre="pad")], 90, 4
    )
    output = analyze_signal(AudioSignal(samples, SR), PipelineOptions(chord_vocabulary="extended"))
    assert {c.suffix for c in output.chords} <= {"", "m", "N"}


def test_detuned_noisy_recording() -> None:
    """A recording 30 cents sharp with background noise is still read correctly."""
    import librosa

    progression = ["G", "Em", "C", "D"]
    samples = render_song([SongSection(progression * 4)], 92, 4)
    detuned = librosa.resample(
        samples, orig_sr=SR, target_sr=int(SR / 2 ** (30 / 1200)), res_type="soxr_hq"
    )
    noise = np.random.default_rng(1).standard_normal(len(detuned)) * 0.02
    output = analyze_signal(
        AudioSignal((detuned + noise).astype(np.float32), SR), PipelineOptions()
    )
    assert 20 <= output.tuning * 100 <= 40
    assert Key(output.key.tonic, Mode(output.key.mode)).name == "G Major"
    bpm = 92 * 2 ** (30 / 1200)
    names = [Chord(c.root, c.suffix).format() for c in output.chords if c.root is not None]
    assert names[:8] == progression * 2
    assert abs(output.tempo.bpm - bpm) / bpm < 0.02
