"""Time signature (3/4 vs 4/4) and downbeat phase estimation.

Heuristic: chords and bass notes tend to change on downbeats, and kick drums tend to
land on them. For each candidate meter and phase we measure how much stronger these cues
are on the candidate downbeats than elsewhere. 4/4 is preferred unless 3/4 is clearly
better, because it is by far the most common meter in popular music.
"""

from __future__ import annotations

import numpy as np

from app.audio.types import BeatGrid, ChromaFeatures, FloatArray, MeterEstimate

MIN_BEATS_FOR_METER = 16
THREE_FOUR_MARGIN = 0.4  # in standard deviations of the cue curve


def _change_curve(matrix: FloatArray) -> FloatArray:
    """1 - cosine similarity between consecutive columns (change *into* column i)."""
    if matrix.shape[1] < 2:
        return np.zeros(matrix.shape[1])
    a, b = matrix[:, :-1], matrix[:, 1:]
    num = np.sum(a * b, axis=0)
    den = np.linalg.norm(a, axis=0) * np.linalg.norm(b, axis=0)
    sim = num / np.maximum(den, 1e-9)
    return np.concatenate([[0.0], 1.0 - sim])


def _zscore(values: FloatArray) -> FloatArray:
    std = float(np.std(values))
    return (values - np.mean(values)) / std if std > 0 else np.zeros_like(values)


def _phase_contrast(curve: FloatArray, period: int, phase: int) -> float:
    idx = np.arange(len(curve))
    mask = (idx - phase) % period == 0
    if not np.any(mask) or np.all(mask):
        return 0.0
    return float(np.mean(curve[mask]) - np.mean(curve[~mask]))


def estimate_meter(grid: BeatGrid, chroma: ChromaFeatures, low_onset: FloatArray) -> MeterEstimate:
    beat_cols = np.where(grid.beat_of_interval >= 0)[0]
    n_beats = len(beat_cols)
    if n_beats < MIN_BEATS_FOR_METER:
        return MeterEstimate(beats_per_bar=4, downbeat_phase=0, confidence=0.2)

    harmonic_change = _zscore(_change_curve(chroma.treble[:, beat_cols]))
    bass_change = _zscore(_change_curve(chroma.bass[:, beat_cols]))
    beat_frames = np.clip(grid.frames[beat_cols], 0, len(low_onset) - 1)
    kick = _zscore(low_onset[beat_frames])
    cue = harmonic_change + 0.6 * bass_change + 0.4 * kick

    best: dict[int, tuple[float, int]] = {}
    for period in (3, 4):
        contrasts = [_phase_contrast(cue, period, phase) for phase in range(period)]
        phase = int(np.argmax(contrasts))
        best[period] = (contrasts[phase], phase)

    score4, phase4 = best[4]
    score3, phase3 = best[3]
    # cue is z-scored: contrasts are in standard deviations
    if score3 > score4 + THREE_FOUR_MARGIN and score3 > 0.5:
        meter, phase, margin, strength = 3, phase3, score3 - score4, score3
    else:
        meter, phase, margin, strength = 4, phase4, score4 - score3, score4

    confidence = 0.5 * float(np.clip(margin / 0.8, 0, 1)) + 0.5 * float(
        np.clip(strength / 1.5, 0, 1)
    )
    return MeterEstimate(beats_per_bar=meter, downbeat_phase=phase, confidence=round(confidence, 2))


def low_frequency_onset(samples: np.ndarray, sr: int, hop: int) -> FloatArray:
    """Onset strength below 200 Hz (kick drum / bass attacks)."""
    import librosa

    env = librosa.onset.onset_strength(
        y=samples, sr=sr, hop_length=hop, n_mels=32, fmax=200.0, aggregate=np.mean
    )
    return np.asarray(env, dtype=np.float64)
