"""Global key estimation.

Stage 1 correlates the song's pitch-class profile with Krumhansl-Kessler key profiles.
Stage 2 (after chord detection) re-ranks the candidates with harmonic evidence:
how much of the song uses chords diatonic to the key, and how prominent the tonic chord
is. Stage 2 mostly resolves relative major/minor confusion (C Major vs A Minor).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from app.audio.types import ChromaFeatures, FloatArray, KeyEstimate
from app.music.keys import Key, Mode

KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Diatonic triads per mode as (interval above tonic, chord suffix). Minor includes the
# harmonic-minor dominant (V), which is very common in practice.
DIATONIC_MAJOR = ((0, ""), (2, "m"), (4, "m"), (5, ""), (7, ""), (9, "m"), (11, "dim"))
DIATONIC_MINOR = ((0, "m"), (2, "dim"), (3, ""), (5, "m"), (7, "m"), (7, ""), (8, ""), (10, ""))

ChordKey = tuple[int, str]  # (root pitch class, base suffix "" | "m" | "dim")


def pitch_class_profile(chroma: ChromaFeatures) -> FloatArray:
    weights = chroma.energy * np.diff(chroma.interval_times)
    profile = chroma.treble @ weights + 0.5 * (chroma.bass @ weights)
    total = float(np.sum(profile))
    return profile / total if total > 0 else profile


def profile_scores(profile: FloatArray) -> dict[Key, float]:
    scores: dict[Key, float] = {}
    if float(np.std(profile)) == 0.0:
        return {Key(pc, mode): 0.0 for pc in range(12) for mode in Mode}
    for tonic in range(12):
        for mode, template in ((Mode.MAJOR, KK_MAJOR), (Mode.MINOR, KK_MINOR)):
            rotated = np.roll(template, tonic)
            scores[Key(tonic, mode)] = float(np.corrcoef(profile, rotated)[0, 1])
    return scores


def diatonic_chords(key: Key) -> set[ChordKey]:
    table = DIATONIC_MAJOR if key.mode is Mode.MAJOR else DIATONIC_MINOR
    return {((key.tonic + interval) % 12, suffix) for interval, suffix in table}


def _harmonic_fit(
    key: Key, durations: Mapping[ChordKey, float], first: ChordKey | None, last: ChordKey | None
) -> float:
    total = sum(durations.values())
    if total <= 0:
        return 0.0
    diatonic = diatonic_chords(key)
    tonic: ChordKey = (key.tonic, "" if key.mode is Mode.MAJOR else "m")
    diatonic_ratio = sum(d for c, d in durations.items() if c in diatonic) / total
    tonic_ratio = durations.get(tonic, 0.0) / total
    cadence = 0.5 * (first == tonic) + 0.5 * (last == tonic)
    return 0.55 * diatonic_ratio + 0.3 * min(1.0, tonic_ratio * 3) + 0.15 * cadence


def estimate_key(
    profile_score_map: Mapping[Key, float],
    chord_durations: Mapping[ChordKey, float] | None = None,
    chord_sequence: Sequence[ChordKey] = (),
) -> KeyEstimate:
    combined: dict[Key, float] = {}
    first = chord_sequence[0] if chord_sequence else None
    last = chord_sequence[-1] if chord_sequence else None
    for key, corr in profile_score_map.items():
        if chord_durations:
            combined[key] = 0.5 * corr + 0.5 * _harmonic_fit(key, chord_durations, first, last)
        else:
            combined[key] = corr

    ranked = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)
    best_key, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin_term = float(np.clip((best_score - second_score) / 0.1, 0.0, 1.0))
    fit_term = float(np.clip((profile_score_map[best_key] - 0.4) / 0.45, 0.0, 1.0))
    confidence = 0.6 * margin_term + 0.4 * fit_term

    return KeyEstimate(
        tonic=best_key.tonic,
        mode=best_key.mode.value,
        confidence=round(confidence, 2),
        scores={key.name: round(score, 4) for key, score in ranked[:5]},
    )
