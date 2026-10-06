"""Song structure: repeated-section detection and cautious section naming.

1. Bar-level features: harmonic chroma + timbre (MFCC) + loudness.
2. Each bar is described by itself and the following bars (4-bar phrase embedding), so
   bars cluster by the *phrase* they belong to rather than by the single chord they hold.
3. Laplacian spectral clustering (McFee & Ellis 2014) on a recurrence graph plus a
   sequential path graph; the number of section types is chosen by the eigengap.
4. Short runs are merged, labels become A, B, C... in order of appearance.
5. Semantic names (Intro, Verse, Chorus, ...) are only *inferred* from position,
   repetition and loudness, flagged as such, and shown only above a confidence threshold.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, replace

import numpy as np

from app.audio.types import FloatArray, IntArray

logger = logging.getLogger(__name__)

PHRASE_BARS = 4
MIN_BARS_FOR_STRUCTURE = 12
MIN_SECTION_BARS = 3
MAX_SECTION_TYPES = 6
NAME_THRESHOLD = 0.5
SILENT_BAR_RATIO = 0.05


@dataclass(frozen=True)
class DetectedSection:
    bar_start: int  # inclusive bar numbers
    bar_end: int
    label: str
    name: str
    name_is_inferred: bool
    name_confidence: float
    confidence: float


def bar_features(beat_features: FloatArray, bar_of_interval: IntArray, n_bars: int) -> FloatArray:
    """Average interval-level columns into bars (bar numbers 0..n_bars-1)."""
    out = np.zeros((beat_features.shape[0], n_bars))
    for bar in range(n_bars):
        cols = bar_of_interval == bar
        if np.any(cols):
            out[:, bar] = beat_features[:, cols].mean(axis=1)
    return out


def _standardize(x: FloatArray) -> FloatArray:
    mean = x.mean(axis=1, keepdims=True)
    std = x.std(axis=1, keepdims=True)
    return np.asarray((x - mean) / np.maximum(std, 1e-9), dtype=np.float64)


def _phrase_embedding(features: FloatArray) -> FloatArray:
    """Describe each bar by the phrase around it (bars i-1 .. i+2, edge-padded)."""
    n = features.shape[1]
    offsets = range(-1, PHRASE_BARS - 1)
    parts = [features[:, np.clip(np.arange(n) + k, 0, n - 1)] for k in offsets]
    return np.vstack(parts)


def novelty_curve(features: FloatArray, half: int = PHRASE_BARS) -> FloatArray:
    """Foote checkerboard novelty on the bar self-similarity matrix.

    High where the ``half`` bars before a bar differ from the ``half`` bars after it.
    """
    norm = features / np.maximum(np.linalg.norm(features, axis=0, keepdims=True), 1e-9)
    ssm = norm.T @ norm
    n = ssm.shape[0]
    novelty = np.zeros(n)
    for b in range(1, n):
        lo, hi = max(0, b - half), min(n, b + half)
        before, after = slice(lo, b), slice(b, hi)
        within = (ssm[before, before].mean() + ssm[after, after].mean()) / 2
        novelty[b] = within - ssm[before, after].mean()
    return novelty


def refine_boundaries(runs: list[list[int]], novelty: FloatArray, phase: int) -> list[list[int]]:
    """Move each boundary up to 2 bars to the strongest novelty, preferring 4-bar phrases."""
    runs = [list(r) for r in runs]
    for k in range(1, len(runs)):
        prev, cur = runs[k - 1], runs[k]
        best, best_score = cur[1], -np.inf
        for b in range(cur[1] - 2, cur[1] + 3):
            if b - prev[1] < 2 or cur[2] - b + 1 < 2:
                continue  # keep at least two bars on each side
            score = novelty[b] + (0.15 if (b - phase) % PHRASE_BARS == 0 else 0.0)
            if score > best_score:
                best, best_score = b, score
        prev[2], cur[1] = best - 1, best
    return runs


def _affinity(embedded: FloatArray, timbre: FloatArray) -> FloatArray:
    import librosa

    n = embedded.shape[1]
    k = max(2, int(np.ceil(np.sqrt(n))))
    recurrence = librosa.segment.recurrence_matrix(
        embedded, k=k, width=PHRASE_BARS, mode="affinity", sym=True
    )
    path_distance = np.sum(np.diff(timbre, axis=1) ** 2, axis=0)
    sigma = float(np.median(path_distance)) or 1.0
    path_sim = np.exp(-path_distance / sigma)
    path = np.diag(path_sim, k=1) + np.diag(path_sim, k=-1)
    deg_path = path.sum(axis=1)
    deg_rec = recurrence.sum(axis=1)
    denom = float(np.sum((deg_path + deg_rec) ** 2)) or 1.0
    mu = float(deg_path.dot(deg_path + deg_rec)) / denom
    return np.asarray(mu * recurrence + (1 - mu) * path, dtype=np.float64)


def _spectral_labels(affinity: FloatArray) -> tuple[IntArray, FloatArray, float]:
    """Cluster bars; returns (labels, per-bar silhouette, eigengap)."""
    from scipy.linalg import eigh
    from scipy.ndimage import median_filter
    from scipy.sparse.csgraph import laplacian
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_samples

    lap = laplacian(affinity, normed=True)
    evals, evecs = eigh(lap)
    evecs = median_filter(evecs, size=(3, 1))
    max_k = min(MAX_SECTION_TYPES, affinity.shape[0] // MIN_SECTION_BARS)
    if max_k < 2:
        return np.zeros(affinity.shape[0], dtype=np.int64), np.zeros(affinity.shape[0]), 0.0
    gaps = np.diff(evals[: max_k + 1])
    k = int(np.argmax(gaps[1:max_k]) + 2)  # k in [2, max_k]
    cum = np.cumsum(evecs**2, axis=1) ** 0.5
    x = evecs[:, :k] / np.maximum(cum[:, k - 1 : k], 1e-9)
    labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(x)
    silhouette = silhouette_samples(x, labels) if len(set(labels)) > 1 else np.zeros(len(labels))
    return np.asarray(labels, dtype=np.int64), np.asarray(silhouette), float(gaps[k - 1])


def _runs(labels: IntArray) -> list[list[int]]:
    """[[label, start, end_inclusive], ...]"""
    runs: list[list[int]] = []
    for i, label in enumerate(labels):
        if runs and runs[-1][0] == label:
            runs[-1][2] = i
        else:
            runs.append([int(label), i, i])
    return runs


def _merge_short_runs(runs: list[list[int]], features: FloatArray) -> list[list[int]]:
    """Absorb runs shorter than MIN_SECTION_BARS into the more similar neighbour."""
    runs = [list(r) for r in runs]
    while len(runs) > 1:
        lengths = [end - start + 1 for _, start, end in runs]
        i = int(np.argmin(lengths))
        if lengths[i] >= MIN_SECTION_BARS:
            break
        _, start, end = runs[i]
        mean = features[:, start : end + 1].mean(axis=1)
        candidates = [j for j in (i - 1, i + 1) if 0 <= j < len(runs)]
        distances = {
            j: float(np.linalg.norm(features[:, runs[j][1] : runs[j][2] + 1].mean(axis=1) - mean))
            for j in candidates
        }
        target = min(candidates, key=distances.__getitem__)
        if target < i:
            runs[target][2] = end
        else:
            runs[target][1] = start
        del runs[i]
        merged: list[list[int]] = []
        for run in runs:  # re-coalesce neighbours that now share a label
            if merged and merged[-1][0] == run[0]:
                merged[-1][2] = run[2]
            else:
                merged.append(run)
        runs = merged
    return runs


def merge_fragments(runs: list[list[int]]) -> list[list[int]]:
    """Join sub-phrase fragments that always occur together.

    If label X is always followed by Y, Y always preceded by X, and one of them is shorter
    than a phrase (< 4 bars), "X Y" is one section split by the clustering (e.g. a chorus
    whose last two bars differ). A 4-bar pre-chorus before an 8-bar chorus is kept.
    """
    runs = [list(r) for r in runs]
    while True:
        labels = [r[0] for r in runs]
        merged = False
        for i in range(len(runs) - 1):
            x, y = labels[i], labels[i + 1]
            if x == y:
                continue
            followers = {labels[j + 1] for j in range(len(runs) - 1) if labels[j] == x}
            leaders = {labels[j - 1] if j > 0 else None for j in range(len(runs)) if labels[j] == y}
            longest = {
                label: max(r[2] - r[1] + 1 for r in runs if r[0] == label) for label in (x, y)
            }
            if followers == {y} and leaders == {x} and min(longest.values()) < PHRASE_BARS:
                out: list[list[int]] = []
                for run in runs:
                    if out and out[-1][0] == x and run[0] == y:
                        out[-1][2] = run[2]
                    else:
                        out.append(run)
                runs, merged = out, True
                break
        if not merged:
            return runs


def _letters(runs: list[list[int]]) -> list[str]:
    mapping: dict[int, str] = {}
    out = []
    for label, _, _ in runs:
        if label not in mapping:
            mapping[label] = chr(ord("A") + len(mapping))
        out.append(mapping[label])
    return out


def infer_names(
    letters: list[str], spans: list[tuple[int, int]], energy: list[float]
) -> list[tuple[str, float]]:
    """Heuristic section names with confidences; ("", 0.0) means "leave unnamed".

    Rules (deliberately conservative):
      Intro/Outro  short first/last section that is quiet or does not recur in the body
      Chorus       the loudest label that repeats in the body
      Pre-Chorus   a repeated label always between another repeated label and the chorus
      Verse        a repeated label first heard before the first chorus
      Bridge       a one-off section after the first chorus, 40-90% into the song
    """
    n = len(letters)
    names: list[tuple[str, float]] = [("", 0.0)] * n
    if n < 2:
        return names
    total_bars = spans[-1][1] - spans[0][0] + 1
    median_energy = float(np.median(energy))

    def short(i: int) -> bool:
        return spans[i][1] - spans[i][0] + 1 <= 0.2 * total_bars

    def quiet(i: int) -> bool:
        return energy[i] < 0.8 * median_energy

    # A quiet intro may return once mid-song (as an interlude); a label that keeps
    # recurring is part of the song body, however quiet.
    inner = Counter(letters[1:-1])

    def edge_like(i: int) -> bool:
        recurrences = inner[letters[i]]
        return short(i) and (recurrences == 0 or (recurrences == 1 and quiet(i)))

    if edge_like(0):
        names[0] = ("Intro", 0.6 + (0.1 if quiet(0) else 0.0))
    if n > 2 and edge_like(n - 1):
        names[-1] = ("Outro", 0.55 + (0.1 if quiet(n - 1) else 0.0))

    body = [i for i in range(n) if not names[i][0]]
    counts = Counter(letters[i] for i in body)
    repeated = [letter for letter, count in counts.items() if count >= 2]
    if not repeated:
        return names

    def mean_energy(letter: str) -> float:
        return float(np.mean([energy[i] for i in body if letters[i] == letter]))

    chorus = max(repeated, key=mean_energy)
    others = [mean_energy(letter) for letter in repeated if letter != chorus]
    strong = not others or mean_energy(chorus) >= 1.1 * max(others)
    first_chorus = letters.index(chorus)

    def neighbours(letter: str, offset: int) -> set[str]:
        return {letters[i + offset] for i in body if letters[i] == letter and 0 <= i + offset < n}

    pre_chorus = {
        letter
        for letter in repeated
        if letter != chorus
        and neighbours(letter, 1) == {chorus}
        and all(prev in repeated and prev != chorus for prev in neighbours(letter, -1))
    }
    for i in body:
        letter = letters[i]
        if letter == chorus:
            names[i] = ("Chorus", 0.6 if strong else 0.45)
        elif letter in pre_chorus:
            names[i] = ("Pre-Chorus", 0.5 if strong else 0.4)
        elif letter in repeated and letters.index(letter) < first_chorus:
            names[i] = ("Verse", 0.55 if strong else 0.45)
        elif counts[letter] == 1 and i > first_chorus and 0.4 <= spans[i][0] / total_bars <= 0.9:
            names[i] = ("Bridge", 0.5 if strong else 0.4)
    return names


def detect_structure(
    chroma: FloatArray,
    timbre: FloatArray,
    energy: FloatArray,
    bar_numbers: IntArray,
) -> tuple[list[DetectedSection], float]:
    """Return sections (by bar number) and an overall structure confidence (0..1)."""
    first_bar = int(bar_numbers.min()) if len(bar_numbers) else 0
    n_bars = int(bar_numbers.max()) + 1 if len(bar_numbers) else 0
    if n_bars - first_bar < MIN_BARS_FOR_STRUCTURE:
        return [], 0.0

    chroma_bars = bar_features(chroma, bar_numbers, n_bars)
    timbre_bars = bar_features(timbre, bar_numbers, n_bars)
    energy_bars = bar_features(energy[np.newaxis, :], bar_numbers, n_bars)[0]

    # Cluster only the sounding part: the pickup bar and silent edges join the
    # neighbouring section afterwards instead of forming sections of their own.
    loud = np.where(energy_bars >= SILENT_BAR_RATIO * float(np.median(energy_bars)))[0]
    loud = loud[loud >= 1] if n_bars > 1 else loud
    if len(loud) < MIN_BARS_FOR_STRUCTURE:
        return [], 0.0
    start, stop = int(loud[0]), int(loud[-1]) + 1
    loudness = np.log(np.maximum(energy_bars[np.newaxis, start:stop], 1e-6))
    feats = np.vstack(
        [
            _standardize(chroma_bars[:, start:stop]),
            _standardize(timbre_bars[:, start:stop]),
            2.0 * _standardize(loudness),
        ]
    )

    try:
        labels, silhouette, eigengap = _spectral_labels(
            _affinity(_phrase_embedding(feats), timbre_bars[:, start:stop])
        )
    except (ValueError, np.linalg.LinAlgError):
        logger.warning("structure clustering failed", exc_info=True)
        return [], 0.0

    runs = _merge_short_runs(_runs(labels), feats)
    runs = refine_boundaries(runs, novelty_curve(feats), phase=0)
    runs = merge_fragments(runs)
    letters = _letters(runs)
    spans = [(start + s, start + e) for _, s, e in runs]
    spans[0] = (first_bar, spans[0][1])
    spans[-1] = (spans[-1][0], n_bars - 1)
    section_energy = [float(energy_bars[s : e + 1].mean()) for s, e in spans]
    names = infer_names(letters, spans, section_energy)

    sections: list[DetectedSection] = []
    for (s, e), letter, (name, name_conf), (_, rs, re_) in zip(
        spans, letters, names, runs, strict=True
    ):
        seg_sil = float(np.mean(silhouette[rs : re_ + 1])) if len(silhouette) else 0.0
        confidence = round(float(np.clip((seg_sil + 0.1) / 0.7, 0.0, 1.0)), 2)
        show = name and name_conf >= NAME_THRESHOLD
        sections.append(
            DetectedSection(
                bar_start=s,
                bar_end=e,
                label=letter,
                name=name if show else f"Section {letter}",
                name_is_inferred=bool(show),
                name_confidence=round(name_conf, 2),
                confidence=confidence,
            )
        )
    overall = float(np.clip((float(np.mean(silhouette)) + 0.1) / 0.7, 0.0, 1.0))
    overall = round(0.8 * overall + 0.2 * min(1.0, eigengap * 5), 2)
    if len(sections) == 1:
        sections = [replace(sections[0], confidence=0.3)]
        overall = 0.3
    return sections, overall
