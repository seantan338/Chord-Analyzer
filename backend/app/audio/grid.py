"""Construction of the beat-synchronous analysis grid."""

from __future__ import annotations

import numpy as np

from app.audio.types import BeatGrid, IntArray

MIN_EDGE_FRAMES = 3


def extend_beats(beats: IntArray, n_frames: int) -> IntArray:
    """Extrapolate the beat grid to the start and end of the audio.

    Beat trackers drop weak beats in quiet intros/outros. Extending the grid with the
    median period keeps those regions beat-aligned (silence becomes its own "N" beats
    instead of being merged into the first chord).
    """
    if len(beats) < 2:
        return beats
    period = float(np.median(np.diff(beats)))
    if period <= 0:
        return beats
    before = np.arange(beats[0] - period, MIN_EDGE_FRAMES - period / 2, -period)[::-1]
    after = np.arange(beats[-1] + period, n_frames - MIN_EDGE_FRAMES, period)
    extended = np.concatenate([before, beats, after])
    return np.round(extended).astype(np.int64)


def build_grid(
    beat_frames: IntArray, n_frames: int, frame_rate: float, duration: float
) -> BeatGrid:
    beats = extend_beats(np.unique(np.asarray(beat_frames, dtype=np.int64)), n_frames)
    beats = np.unique(beats[(beats >= 0) & (beats < n_frames - MIN_EDGE_FRAMES)])
    if len(beats) and beats[0] <= MIN_EDGE_FRAMES:
        beats[0] = 0  # first beat is effectively at the start: no pre-roll
    has_preroll = len(beats) == 0 or beats[0] > 0
    frames = (
        np.concatenate([[0], beats, [n_frames]])
        if has_preroll
        else np.concatenate([beats, [n_frames]])
    )
    frames = np.unique(frames)
    n_intervals = len(frames) - 1
    beat_index = np.arange(n_intervals, dtype=np.int64) - (1 if has_preroll else 0)
    times = frames / frame_rate
    times[-1] = duration
    return BeatGrid(frames=frames, times=times.astype(np.float64), beat_of_interval=beat_index)
