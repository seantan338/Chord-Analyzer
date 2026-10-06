"""Intermediate data structures passed between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

SAMPLE_RATE = 22050
HOP_LENGTH = 512


@dataclass(frozen=True)
class AudioSignal:
    samples: npt.NDArray[np.float32]
    sample_rate: int

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate


@dataclass(frozen=True)
class TempoEstimate:
    bpm: float
    confidence: float
    beat_times: FloatArray  # seconds
    beat_frames: IntArray
    alternatives: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class MeterEstimate:
    beats_per_bar: int
    downbeat_phase: int  # index of the first downbeat in the beat list
    confidence: float

    @property
    def time_signature(self) -> str:
        return f"{self.beats_per_bar}/4"


@dataclass(frozen=True)
class ChromaFeatures:
    """Beat-synchronous chroma. Column ``i`` covers beat interval ``i``."""

    treble: FloatArray  # (12, n_intervals), L2-normalised per column
    bass: FloatArray  # (12, n_intervals), max-normalised per column
    energy: FloatArray  # (n_intervals,) harmonic RMS per interval
    interval_times: FloatArray  # (n_intervals + 1,) boundaries in seconds
    frame_treble: FloatArray  # (12, n_frames) frame-level chroma for key detection


@dataclass(frozen=True)
class KeyEstimate:
    tonic: int
    mode: str  # "major" | "minor"
    confidence: float
    scores: dict[str, float]  # key name -> score, for alternatives


@dataclass(frozen=True)
class DetectedChord:
    """A chord over a run of consecutive beat intervals [start_beat, end_beat)."""

    start_beat: int
    end_beat: int
    start: float
    end: float
    root: int | None  # None = no chord
    suffix: str
    bass: int | None
    confidence: float


@dataclass(frozen=True)
class BeatGrid:
    """Analysis grid: interval ``i`` spans ``times[i]`` to ``times[i + 1]``.

    Interval 0 may be a *pre-roll* (audio before the first detected beat), marked with
    beat index -1. All other intervals start on a detected beat.
    """

    frames: IntArray  # (n_intervals + 1,) boundaries in STFT frames
    times: FloatArray  # (n_intervals + 1,) boundaries in seconds, last == duration
    beat_of_interval: IntArray  # (n_intervals,), -1 for pre-roll

    @property
    def n_intervals(self) -> int:
        return len(self.frames) - 1

    @property
    def has_preroll(self) -> bool:
        return bool(self.n_intervals and self.beat_of_interval[0] < 0)

    @property
    def durations(self) -> FloatArray:
        return np.diff(self.times)

    @property
    def beat_times(self) -> FloatArray:
        start = 1 if self.has_preroll else 0
        return self.times[start:-1]
