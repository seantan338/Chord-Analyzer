"""Tempo estimation and beat tracking with explicit half-/double-time resolution."""

from __future__ import annotations

import logging

import numpy as np

from app.audio.types import FloatArray, IntArray, TempoEstimate

logger = logging.getLogger(__name__)

MIN_BPM = 40.0
MAX_BPM = 220.0
PRIOR_CENTER_BPM = 110.0
PRIOR_SIGMA_OCTAVES = 0.6
MIN_BEATS = 8


def onset_envelope(samples: np.ndarray, sr: int, hop: int) -> FloatArray:
    import librosa

    env = librosa.onset.onset_strength(y=samples, sr=sr, hop_length=hop, aggregate=np.median)
    return np.asarray(env, dtype=np.float64)


def tempo_prior(bpm: float) -> float:
    """Log-normal preference for musically common tempi (peaks around 110 BPM)."""
    return float(np.exp(-0.5 * (np.log2(bpm / PRIOR_CENTER_BPM) / PRIOR_SIGMA_OCTAVES) ** 2))


class _PulseStrength:
    """Global autocorrelation strength of the onset envelope at a given tempo."""

    def __init__(self, env: FloatArray, sr: int, hop: int) -> None:
        import librosa

        tg = librosa.feature.tempogram(onset_envelope=env, sr=sr, hop_length=hop)
        self.ac = np.mean(tg, axis=1)
        self.ac[0] = 0.0
        self.frame_rate = sr / hop
        lags = np.arange(len(self.ac))
        valid = (lags >= self._lag(MAX_BPM)) & (lags <= self._lag(MIN_BPM))
        self.max_strength = float(np.max(self.ac[valid])) if np.any(valid) else 1.0

    def _lag(self, bpm: float) -> float:
        return 60.0 * self.frame_rate / bpm

    def __call__(self, bpm: float) -> float:
        lag = self._lag(bpm)
        value = float(np.interp(lag, np.arange(len(self.ac)), self.ac))
        return value / (self.max_strength or 1.0)


def _offbeat_ratio(env: FloatArray, beat_frames: IntArray) -> float:
    """Onset strength half-way between beats relative to on the beats.

    Close to 1 means the midpoints are as strong as the beats: the true pulse may be
    twice as fast (the classic "41 BPM vs 82 BPM" half-time error).
    """
    if len(beat_frames) < 4:
        return 0.0
    mids = ((beat_frames[:-1] + beat_frames[1:]) // 2).astype(int)
    on = float(np.mean(env[beat_frames[:-1]]))
    off = float(np.mean(env[mids]))
    return off / on if on > 0 else 0.0


def _track(env: FloatArray, sr: int, hop: int, bpm: float) -> IntArray:
    import librosa

    _, beats = librosa.beat.beat_track(
        onset_envelope=env, sr=sr, hop_length=hop, bpm=bpm, tightness=100, trim=True, units="frames"
    )
    return np.asarray(beats, dtype=np.int64)


def _fallback_grid(env: FloatArray, sr: int, hop: int, bpm: float) -> IntArray:
    period = 60.0 * sr / hop / bpm
    start = int(np.argmax(env > 0.1 * np.max(env))) if np.max(env) > 0 else 0
    return np.arange(start, len(env), period).astype(np.int64)


def _refined_bpm(beat_times: FloatArray) -> float:
    """Average tempo from a line fit through beat times (sub-frame precision).

    Beat indices are recovered from the median period, so a missed beat does not skew
    the fit.
    """
    ibis = np.diff(beat_times)
    median = float(np.median(ibis))
    # Frame quantisation makes IBIs alternate (e.g. 0.720/0.743 s); average the
    # plausible ones instead of taking the median of two quantised values.
    plausible = ibis[(ibis > 0.7 * median) & (ibis < 1.3 * median)]
    period = float(np.mean(plausible)) if len(plausible) else median
    indices = np.round((beat_times - beat_times[0]) / period)
    if len(np.unique(indices)) < 2:
        return 60.0 / period
    slope = float(np.polyfit(indices, beat_times, 1)[0])
    return 60.0 / slope if slope > 0 else 60.0 / period


def estimate_tempo(env: FloatArray, sr: int, hop: int) -> TempoEstimate:
    import librosa

    strength = _PulseStrength(env, sr, hop)
    initial = float(
        librosa.feature.tempo(
            onset_envelope=env, sr=sr, hop_length=hop, start_bpm=PRIOR_CENTER_BPM
        )[0]
    )
    raw = {initial / 2, initial, initial * 2, initial * 2 / 3, initial * 3 / 2}
    candidates = sorted(c for c in raw if MIN_BPM <= c <= MAX_BPM) or [initial]
    scores = {c: strength(c) * tempo_prior(c) for c in candidates}
    best = max(scores, key=lambda c: scores[c])

    beats = _track(env, sr, hop, best)
    # Half-time check: strong onsets between the beats suggest the doubled tempo.
    doubled = best * 2
    if (
        doubled <= MAX_BPM
        and _offbeat_ratio(env, beats) > 0.8
        and tempo_prior(doubled) >= 0.5 * tempo_prior(best)
    ):
        logger.debug("half-time correction %.1f -> %.1f", best, doubled)
        scores[doubled] = max(scores.get(doubled, 0.0), scores[best] * 1.01)
        best = doubled
        beats = _track(env, sr, hop, best)

    tracked_ok = len(beats) >= MIN_BEATS
    if not tracked_ok:
        beats = _fallback_grid(env, sr, hop, best)

    beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=hop)
    ibis = np.diff(beat_times)
    bpm = _refined_bpm(beat_times) if len(ibis) else best

    cv = float(np.std(ibis) / np.mean(ibis)) if len(ibis) > 1 else 1.0
    regularity = float(np.clip(1.0 - cv / 0.12, 0.0, 1.0))
    pulse = float(np.clip(strength(bpm), 0.0, 1.0))
    ranked = sorted(scores.values(), reverse=True)
    ambiguity = ranked[1] / ranked[0] if len(ranked) > 1 and ranked[0] > 0 else 0.0
    confidence = 0.45 * regularity + 0.35 * pulse + 0.2 * (1.0 - ambiguity)
    if not tracked_ok:
        confidence *= 0.4

    # Only half/double time is reported: those are the ambiguities musicians recognise.
    alternatives = sorted(
        {
            round(bpm * ratio, 1)
            for c, s in scores.items()
            for ratio in (0.5, 2.0)
            if abs(c - best * ratio) < 0.5 and s >= 0.5 * scores[best]
        }
    )
    return TempoEstimate(
        bpm=round(bpm, 1),
        confidence=round(float(np.clip(confidence, 0.0, 1.0)), 2),
        beat_times=np.asarray(beat_times, dtype=np.float64),
        beat_frames=beats,
        alternatives=alternatives,
    )
