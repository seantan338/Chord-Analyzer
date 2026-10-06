"""Chord candidate scoring on beat-synchronous chroma (24 major/minor triads + no-chord).

Each grid interval gets a score per chord state from:
  * cosine similarity between treble chroma and a binary triad template, and
  * a bass term rewarding chords whose root is the loudest bass pitch class.
The scores become log-emission probabilities for the HMM in ``chord_smoothing``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.audio.types import ChromaFeatures, FloatArray

N_STATES = 25  # 12 major, 12 minor, no-chord
NO_CHORD_STATE = 24

BASS_WEIGHT = 0.18
NO_CHORD_BASE_SCORE = 0.64  # flat (noise-like) chroma scores ~0.58 against any triad
LOW_ENERGY_RATIO = 0.08  # intervals quieter than this x median are treated as no-chord
EMISSION_SHARPNESS = 16.0


@dataclass(frozen=True)
class ChordState:
    root: int | None
    suffix: str  # "" (major) | "m" (minor) | "N"


STATES: tuple[ChordState, ...] = tuple(
    [ChordState(pc, "") for pc in range(12)]
    + [ChordState(pc, "m") for pc in range(12)]
    + [ChordState(None, "N")]
)


def triad_templates() -> FloatArray:
    """(24, 12) L2-normalised binary templates for major and minor triads."""
    templates = np.zeros((24, 12))
    for root in range(12):
        templates[root, [root, (root + 4) % 12, (root + 7) % 12]] = 1.0
        templates[12 + root, [root, (root + 3) % 12, (root + 7) % 12]] = 1.0
    return np.asarray(
        templates / np.linalg.norm(templates, axis=1, keepdims=True), dtype=np.float64
    )


TEMPLATES = triad_templates()


def triad_similarity(treble: FloatArray) -> FloatArray:
    """(24, n) cosine similarity of each interval to each triad template."""
    return np.asarray(TEMPLATES @ treble, dtype=np.float64)


def emission_scores(chroma: ChromaFeatures) -> FloatArray:
    """(25, n) raw scores; higher means the interval sounds more like that state."""
    sims = triad_similarity(chroma.treble)
    roots = np.concatenate([np.arange(12), np.arange(12)])
    bass_term = chroma.bass[roots, :] - 0.5
    scores = np.empty((N_STATES, chroma.treble.shape[1]))
    scores[:24] = sims + BASS_WEIGHT * bass_term

    energy = chroma.energy
    reference = float(np.median(energy[energy > 0])) if np.any(energy > 0) else 0.0
    quiet = energy < LOW_ENERGY_RATIO * reference if reference > 0 else np.ones_like(energy, bool)
    scores[NO_CHORD_STATE] = NO_CHORD_BASE_SCORE
    scores[NO_CHORD_STATE, quiet] = 2.0
    return scores


def log_emissions(scores: FloatArray) -> FloatArray:
    logits = EMISSION_SHARPNESS * scores
    logits -= logits.max(axis=0, keepdims=True)
    return np.asarray(logits - np.log(np.exp(logits).sum(axis=0, keepdims=True)), dtype=np.float64)
