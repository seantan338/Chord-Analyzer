"""Temporal smoothing of chord candidates with a beat-position-aware HMM.

Chord changes are most likely on downbeats, less likely mid-bar and rare on weak beats.
A mild key prior favours diatonic chords without forbidding borrowed ones.
"""

from __future__ import annotations

import numpy as np

from app.audio.chord_detection import N_STATES, NO_CHORD_STATE, STATES
from app.audio.confidence import chord_confidence
from app.audio.key_detection import diatonic_chords
from app.audio.types import BeatGrid, ChromaFeatures, DetectedChord, FloatArray, IntArray
from app.music.keys import Key

STAY_DOWNBEAT = 0.55
STAY_HALF_BAR = 0.8
STAY_WEAK_BEAT = 0.95
STAY_PREROLL = 0.5
WEIGHT_DIATONIC = 1.0
WEIGHT_NON_DIATONIC = 0.55
WEIGHT_NO_CHORD = 0.35
MIN_CONFIDENT_SINGLE_BEAT = 0.45


def bar_positions(grid: BeatGrid, beats_per_bar: int, phase: int) -> IntArray:
    """Position of each interval within its bar (0 = downbeat, -1 = pre-roll)."""
    beats = grid.beat_of_interval
    return np.where(beats >= 0, (beats - phase) % beats_per_bar, -1).astype(np.int64)


def stay_probabilities(positions: IntArray, beats_per_bar: int) -> FloatArray:
    stay = np.full(len(positions), STAY_WEAK_BEAT)
    stay[positions == 0] = STAY_DOWNBEAT
    if beats_per_bar == 4:
        stay[positions == 2] = STAY_HALF_BAR
    stay[positions < 0] = STAY_PREROLL
    return stay


def entry_weights(key: Key | None) -> FloatArray:
    weights = np.full(N_STATES, WEIGHT_DIATONIC if key is None else WEIGHT_NON_DIATONIC)
    if key is not None:
        diatonic = diatonic_chords(key)
        for index, state in enumerate(STATES[:NO_CHORD_STATE]):
            if (state.root, state.suffix) in diatonic:
                weights[index] = WEIGHT_DIATONIC
    weights[NO_CHORD_STATE] = WEIGHT_NO_CHORD
    return weights


def viterbi(log_emit: FloatArray, stay: FloatArray, weights: FloatArray) -> IntArray:
    n_states, n_steps = log_emit.shape
    if n_steps == 0:
        return np.zeros(0, dtype=np.int64)
    log_w = np.log(weights)
    total = float(weights.sum())
    log_leave_norm = np.log(total - weights)  # normaliser for leaving state j
    delta = log_w - np.log(total) + log_emit[:, 0]
    back = np.zeros((n_steps, n_states), dtype=np.int64)
    for t in range(1, n_steps):
        p_stay = float(stay[t])
        log_a = np.log1p(-p_stay) + log_w[np.newaxis, :] - log_leave_norm[:, np.newaxis]
        np.fill_diagonal(log_a, np.log(p_stay))
        candidates = delta[:, np.newaxis] + log_a
        back[t] = np.argmax(candidates, axis=0)
        delta = candidates[back[t], np.arange(n_states)] + log_emit[:, t]
    path = np.zeros(n_steps, dtype=np.int64)
    path[-1] = int(np.argmax(delta))
    for t in range(n_steps - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def _runs(path: IntArray) -> list[tuple[int, int, int]]:
    """(state, start, end) for runs of identical states, end exclusive."""
    runs: list[tuple[int, int, int]] = []
    start = 0
    for i in range(1, len(path) + 1):
        if i == len(path) or path[i] != path[start]:
            runs.append((int(path[start]), start, i))
            start = i
    return runs


def _segment_profile(chroma: ChromaFeatures, start: int, end: int) -> FloatArray:
    weights = np.diff(chroma.interval_times)[start:end] * (chroma.energy[start:end] + 1e-9)
    return np.asarray(chroma.treble[:, start:end] @ weights, dtype=np.float64)


def _absorb_unstable_runs(
    runs: list[tuple[int, int, int]], scores: FloatArray, confidences: list[float]
) -> list[tuple[int, int, int]]:
    """Merge single-interval, low-confidence runs into the neighbour that fits better."""
    if len(runs) < 2:
        return runs
    out: list[tuple[int, int, int]] = []
    for i, (state, start, end) in enumerate(runs):
        if end - start == 1 and confidences[i] < MIN_CONFIDENT_SINGLE_BEAT:
            neighbours = [runs[j][0] for j in (i - 1, i + 1) if 0 <= j < len(runs)]
            state = max(neighbours, key=lambda s: float(scores[s, start:end].mean()))
        out.append((state, start, end))
    return _coalesce(out)


def _coalesce(runs: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for state, start, end in runs:
        if out and out[-1][0] == state:
            out[-1] = (state, out[-1][1], end)
        else:
            out.append((state, start, end))
    return out


def smooth_chords(
    chroma: ChromaFeatures,
    scores: FloatArray,
    log_emit: FloatArray,
    grid: BeatGrid,
    beats_per_bar: int,
    downbeat_phase: int,
    key: Key | None,
) -> list[DetectedChord]:
    positions = bar_positions(grid, beats_per_bar, downbeat_phase)
    path = viterbi(log_emit, stay_probabilities(positions, beats_per_bar), entry_weights(key))
    runs = _runs(path)
    quiet = scores[NO_CHORD_STATE] >= 2.0

    def conf(state: int, start: int, end: int) -> float:
        return chord_confidence(
            _segment_profile(chroma, start, end), state, end - start, bool(np.all(quiet[start:end]))
        )

    runs = _absorb_unstable_runs(runs, scores, [conf(*run) for run in runs])
    segments: list[DetectedChord] = []
    for state, start, end in runs:
        chord_state = STATES[state]
        segments.append(
            DetectedChord(
                start_beat=start,
                end_beat=end,
                start=float(grid.times[start]),
                end=float(grid.times[end]),
                root=chord_state.root,
                suffix=chord_state.suffix if chord_state.root is not None else "N",
                bass=None,
                confidence=conf(state, start, end),
            )
        )
    return segments
