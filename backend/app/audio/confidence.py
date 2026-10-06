"""Confidence heuristics.

Scores are *relative* indicators in [0, 1] built from template fit and margins, not
calibrated probabilities. The UI maps them to High / Medium / Low only.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from app.audio.chord_detection import NO_CHORD_STATE, TEMPLATES
from app.audio.types import FloatArray

ConfidenceLevel = Literal["high", "medium", "low"]

HIGH_THRESHOLD = 0.75
MEDIUM_THRESHOLD = 0.5


def confidence_level(value: float) -> ConfidenceLevel:
    if value >= HIGH_THRESHOLD:
        return "high"
    if value >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def chord_confidence(mean_treble: FloatArray, state: int, n_beats: int, quiet: bool) -> float:
    norm = float(np.linalg.norm(mean_treble))
    sims = TEMPLATES @ (mean_treble / norm) if norm > 0 else np.zeros(TEMPLATES.shape[0])
    if state == NO_CHORD_STATE:
        if quiet:
            return 0.8
        return round(float(np.clip((0.78 - float(np.max(sims))) / 0.2, 0.0, 1.0)), 2)
    fit = float(sims[state])
    margin = fit - float(np.max(np.delete(sims, state)))
    fit_score = float(np.clip((fit - 0.6) / 0.3, 0.0, 1.0))
    margin_score = float(np.clip(margin / 0.1, 0.0, 1.0))
    duration_factor = float(np.clip(0.6 + 0.1 * n_beats, 0.6, 1.0))
    return round((0.55 * fit_score + 0.45 * margin_score) * duration_factor, 2)


def duration_weighted_mean(values: list[float], durations: list[float]) -> float:
    total = sum(durations)
    if total <= 0 or not values:
        return 0.0
    return round(sum(v * d for v, d in zip(values, durations, strict=True)) / total, 2)
