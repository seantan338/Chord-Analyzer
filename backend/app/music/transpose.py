"""Chord and key transposition (pure functions).

    transpose_symbol("G/B", 2)            -> "A/C#"
    transpose_symbol("F#m7", -2)          -> "Em7"
    transpose_symbol("A#", 0, key=F major) -> "Bb"   (respelled for the key)

When a target key is given, notes are spelled by scale degree in that key (Bb in F
major, A# in B major). Without a key, the common chart spelling is used
(C# Eb F# Ab Bb).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.music.chords import NO_CHORD, Chord, ChordParseError, is_no_chord, parse_chord
from app.music.keys import Key
from app.music.notes import Spelling


def transpose_chord(chord: Chord, semitones: int) -> Chord:
    return Chord(
        root=(chord.root + semitones) % 12,
        suffix=chord.suffix,
        bass=None if chord.bass is None else (chord.bass + semitones) % 12,
    )


def transpose_symbol(
    symbol: str, semitones: int, key: Key | None = None, spelling: Spelling = Spelling.DEFAULT
) -> str:
    """Transpose a chord symbol. ``key`` is the key *after* transposition (for spelling).

    Unparseable symbols are returned unchanged rather than raising, so a single odd
    label never breaks a whole chord sheet.
    """
    if is_no_chord(symbol):
        return NO_CHORD
    try:
        chord = parse_chord(symbol)
    except ChordParseError:
        return symbol
    return transpose_chord(chord, semitones).format(key=key, spelling=spelling)


def transpose_progression(
    symbols: Sequence[str], semitones: int, key: Key | None = None
) -> list[str]:
    return [transpose_symbol(s, semitones, key) for s in symbols]


def normalize_semitones(semitones: int) -> int:
    """Map any shift to the equivalent one in [-5, +6] (e.g. +11 -> -1)."""
    shift = semitones % 12
    return shift - 12 if shift > 6 else shift
