"""Second-pass chord refinement: 7ths, suspended, diminished and slash chords.

Stability first: the HMM only decides between 24 triads. A segment is upgraded to a
richer chord only when the extra note is clearly present (and, for sus/dim, the replaced
note is clearly absent). Otherwise the plain triad is kept. Every refinement is local to
one segment, so a wrong guess never spreads.
"""

from __future__ import annotations

from dataclasses import replace
from itertools import pairwise

import numpy as np

from app.audio.types import ChromaFeatures, DetectedChord, FloatArray, IntArray

MIN_CONFIDENCE = 0.5
# A diminished chord fits the minor template poorly *because* its fifth is flattened, so
# low-confidence minor segments are still tested for "dim" (and only for "dim").
MIN_CONFIDENCE_DIM = 0.15
MIN_BEATS = 2
EXTENSION_RATIO = 0.62  # added note vs. mean of triad notes
SUBSTITUTE_RATIO = 0.7  # sus/dim note vs. the notes it keeps
ABSENT_RATIO = 0.35  # replaced note must be this weak
SLASH_BASS_RATIO = 1.3
BASS_PEAKINESS = 1.6


def _profile(matrix: FloatArray, chroma: ChromaFeatures, seg: DetectedChord) -> FloatArray:
    weights = np.diff(chroma.interval_times)[seg.start_beat : seg.end_beat]
    profile = matrix[:, seg.start_beat : seg.end_beat] @ weights
    peak = float(np.max(profile))
    return np.asarray(profile / peak if peak > 0 else profile, dtype=np.float64)


def _note(profile: FloatArray, root: int, interval: int) -> float:
    return float(profile[(root + interval) % 12])


def refine_quality(profile: FloatArray, root: int, minor: bool) -> str:
    """Return the chord suffix best supported by ``profile`` (a max-normalised chroma)."""
    third = 3 if minor else 4
    r, t, f = _note(profile, root, 0), _note(profile, root, third), _note(profile, root, 7)
    triad_mean = (r + t + f) / 3
    b7, maj7 = _note(profile, root, 10), _note(profile, root, 11)

    # Substitutions: the new note must be strong relative to the *weaker* kept note and
    # the replaced note weak relative to the *stronger* one. This keeps the test stable
    # whether or not the root is inflated (or attenuated) by the bass line.
    if minor:
        b5 = _note(profile, root, 6)
        if b5 >= SUBSTITUTE_RATIO * min(r, t) and f <= ABSENT_RATIO * max(r, t):
            return "dim"
        if b7 >= EXTENSION_RATIO * triad_mean and b7 > maj7:
            return "m7"
        return "m"

    fourth, second = _note(profile, root, 5), _note(profile, root, 2)
    if t <= ABSENT_RATIO * max(r, f):
        if fourth >= SUBSTITUTE_RATIO * min(r, f) and fourth > second:
            return "sus4"
        if second >= SUBSTITUTE_RATIO * min(r, f):
            return "sus2"
    if b7 >= EXTENSION_RATIO * triad_mean and b7 > 1.2 * maj7:
        return "7"
    if maj7 >= EXTENSION_RATIO * triad_mean and maj7 > 1.2 * b7:
        return "maj7"
    return ""


def detect_bass(profile: FloatArray, root: int, chord_tones: tuple[int, ...]) -> int | None:
    """Bass pitch class for a slash chord, or None when the root is (or may be) in the bass."""
    if float(np.max(profile)) < BASS_PEAKINESS * float(np.median(profile)):
        return None  # no clear bass line
    bass = int(np.argmax(profile))
    if bass == root or bass not in chord_tones:
        return None
    if profile[bass] < SLASH_BASS_RATIO * profile[root]:
        return None
    return bass


_SUFFIX_INTERVALS = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "sus4": (0, 5, 7),
    "sus2": (0, 2, 7),
    "dim": (0, 3, 6),
}


def _bar_pieces(seg: DetectedChord, positions: IntArray) -> list[tuple[int, int]]:
    """Split a segment's interval range at downbeats: [(start, end), ...]."""
    cuts = [i for i in range(seg.start_beat + 1, seg.end_beat) if positions[i] == 0]
    bounds = [seg.start_beat, *cuts, seg.end_beat]
    return list(pairwise(bounds))


def template_fit(profile: FloatArray, tones: tuple[int, ...]) -> float:
    template = np.zeros(12)
    template[list(tones)] = 1.0
    denom = float(np.linalg.norm(profile) * np.linalg.norm(template))
    return float(profile @ template) / denom if denom > 0 else 0.0


def _refine_piece(seg: DetectedChord, chroma: ChromaFeatures) -> DetectedChord:
    assert seg.root is not None
    profile = _profile(chroma.treble, chroma, seg)
    suffix = refine_quality(profile, seg.root, seg.suffix == "m")
    if seg.confidence < MIN_CONFIDENCE and suffix != "dim":
        return seg
    tones = tuple((seg.root + i) % 12 for i in _SUFFIX_INTERVALS[suffix])
    bass = detect_bass(_profile(chroma.bass, chroma, seg), seg.root, tones)
    confidence = seg.confidence
    if suffix == "dim":
        fit = float(np.clip((template_fit(profile, tones) - 0.6) / 0.3, 0.0, 1.0))
        confidence = round(max(confidence, fit * 0.9), 2)
    return replace(seg, suffix=suffix, bass=bass, confidence=confidence)


def refine_chords(
    chords: list[DetectedChord], chroma: ChromaFeatures, positions: IntArray
) -> list[DetectedChord]:
    """Refine each segment bar by bar (so Dsus4 -> D within one "D" run is found), then
    merge neighbouring pieces that ended up with the same label."""
    times = chroma.interval_times
    refined: list[DetectedChord] = []
    for seg in chords:
        threshold = MIN_CONFIDENCE_DIM if seg.suffix == "m" else MIN_CONFIDENCE
        if seg.root is None or seg.confidence < threshold:
            refined.append(seg)
            continue
        for start, end in _bar_pieces(seg, positions):
            piece = replace(
                seg,
                start_beat=start,
                end_beat=end,
                start=float(times[start]),
                end=float(times[end]),
            )
            if end - start >= MIN_BEATS:
                piece = _refine_piece(piece, chroma)
            same = (
                refined
                and refined[-1].root == piece.root
                and refined[-1].suffix == piece.suffix
                and refined[-1].bass == piece.bass
                and refined[-1].end_beat == piece.start_beat
            )
            if same:
                refined[-1] = replace(refined[-1], end_beat=piece.end_beat, end=piece.end)
            else:
                refined.append(piece)
    return refined
