"""Guitar capo suggestions.

For each capo position the song is re-expressed as the chord *shapes* a guitarist would
play. A shape set is rated by how much of the song (by duration) uses easy open chords.
Suggestions are only offered when they clearly beat playing without a capo.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.music.chords import Chord, ChordFamily, ChordParseError, is_no_chord, parse_chord
from app.music.keys import Key
from app.music.simplifier import simplify_chord

MAX_CAPO = 7
MAX_SUGGESTIONS = 3
ALREADY_EASY = 0.85
MIN_IMPROVEMENT = 0.15
MIN_PLAYABILITY = 0.6

# Ease of each simplified triad shape on guitar (1.0 = open chord).
_OPEN_MAJOR = {0: 1.0, 2: 1.0, 4: 1.0, 7: 1.0, 9: 1.0, 5: 0.6}  # C D E G A, F (small barre)
_OPEN_MINOR = {9: 1.0, 2: 1.0, 4: 1.0, 11: 0.5}  # Am Dm Em, Bm (barre)
_BARRE_SCORE = 0.2


@dataclass(frozen=True)
class CapoOption:
    capo: int
    play_key: Key
    play_chords: list[str]
    playability: float


@dataclass(frozen=True)
class CapoAdvice:
    original_playability: float
    options: list[CapoOption]
    note: str


def shape_ease(chord: Chord) -> float:
    triad = simplify_chord(chord)
    table = _OPEN_MINOR if triad.family is ChordFamily.MINOR else _OPEN_MAJOR
    return table.get(triad.root, _BARRE_SCORE)


def _parse_timed(chords: Sequence[tuple[str, float]]) -> list[tuple[Chord, float]]:
    parsed: list[tuple[Chord, float]] = []
    for symbol, duration in chords:
        if is_no_chord(symbol) or duration <= 0:
            continue
        try:
            parsed.append((parse_chord(symbol), duration))
        except ChordParseError:
            continue
    return parsed


def playability(chords: Sequence[tuple[Chord, float]], shift: int) -> float:
    total = sum(d for _, d in chords)
    if total <= 0:
        return 0.0
    eased = sum(shape_ease(Chord((c.root + shift) % 12, c.suffix, c.bass)) * d for c, d in chords)
    return round(eased / total, 2)


def _distinct_shapes(chords: Sequence[tuple[Chord, float]], shift: int, key: Key) -> list[str]:
    seen: list[str] = []
    for chord, _ in chords:
        shape = simplify_chord(Chord((chord.root + shift) % 12, chord.suffix)).format(key=key)
        if shape not in seen:
            seen.append(shape)
    return seen[:8]


def suggest_capo(song_key: Key, timed_chords: Sequence[tuple[str, float]]) -> CapoAdvice:
    """``timed_chords`` are (chord symbol, duration seconds) pairs in song order."""
    chords = _parse_timed(timed_chords)
    if not chords:
        return CapoAdvice(0.0, [], "No chords detected, so no capo advice.")

    base = playability(chords, 0)
    if base >= ALREADY_EASY:
        return CapoAdvice(base, [], f"{song_key.name} is already guitar-friendly; no capo needed.")

    options: list[CapoOption] = []
    for capo in range(1, MAX_CAPO + 1):
        score = playability(chords, -capo)
        if score >= MIN_PLAYABILITY and score >= base + MIN_IMPROVEMENT:
            play_key = song_key.transposed(-capo)
            options.append(
                CapoOption(capo, play_key, _distinct_shapes(chords, -capo, play_key), score)
            )
    # Prefer easier shapes, then lower capo positions (less tension, more range).
    options.sort(key=lambda o: (-(o.playability - 0.02 * o.capo), o.capo))
    options = options[:MAX_SUGGESTIONS]
    if not options:
        return CapoAdvice(base, [], "No capo position makes this song clearly easier.")
    best = options[0]
    note = f"Capo {best.capo} and play {best.play_key.name} shapes for the easiest chords."
    return CapoAdvice(base, options, note)
