"""Beginner chord simplification: any chord -> plain major or minor triad.

    Cmaj7 -> C    Am7 -> Am    Fadd9 -> F    Gsus4 -> G    G/B -> G
    Bdim -> Bm    Bm7b5 -> Bm  Caug -> C     E5 -> E

Diminished chords map to minor (closest triad sharing root and minor third).
"""

from __future__ import annotations

from app.music.chords import NO_CHORD, Chord, ChordFamily, ChordParseError, is_no_chord, parse_chord
from app.music.keys import Key
from app.music.notes import Spelling

_MINOR_FAMILIES = (ChordFamily.MINOR, ChordFamily.DIMINISHED)


def simplify_chord(chord: Chord) -> Chord:
    suffix = "m" if chord.family in _MINOR_FAMILIES else ""
    return Chord(root=chord.root, suffix=suffix, bass=None)


def simplify_symbol(
    symbol: str, key: Key | None = None, spelling: Spelling = Spelling.DEFAULT
) -> str:
    """Simplify a chord symbol; unknown symbols are returned unchanged."""
    if is_no_chord(symbol):
        return NO_CHORD
    try:
        chord = parse_chord(symbol)
    except ChordParseError:
        return symbol
    return simplify_chord(chord).format(key=key, spelling=spelling)
