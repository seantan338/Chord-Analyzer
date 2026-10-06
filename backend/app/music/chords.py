"""Chord symbol parsing and formatting.

A chord symbol is modelled as ``root + suffix [+ /bass]``. The suffix is kept verbatim so
transposition never loses information (``F#m7b5`` -> ``Em7b5``). A coarse *family* is
derived from the suffix for simplification and diatonic checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum

from app.music.keys import Key
from app.music.notes import NoteParseError, Spelling, note_name, parse_note

NO_CHORD = "N"

_CHORD_RE = re.compile(r"^([A-G][#b♯♭]?)([^/]*)(?:/([A-G][#b♯♭]?))?$")


class ChordFamily(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    DIMINISHED = "diminished"
    AUGMENTED = "augmented"
    SUSPENDED = "suspended"
    POWER = "power"


class ChordParseError(ValueError):
    pass


# Canonical suffixes used by the detector, with their intervals above the root.
QUALITY_INTERVALS: dict[str, tuple[int, ...]] = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "m7b5": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9),
    "6": (0, 4, 7, 9),
    "m6": (0, 3, 7, 9),
    "add9": (0, 2, 4, 7),
    "madd9": (0, 2, 3, 7),
}


@dataclass(frozen=True)
class Chord:
    root: int
    suffix: str = ""
    bass: int | None = None

    @property
    def family(self) -> ChordFamily:
        return suffix_family(self.suffix)

    @property
    def is_minor_like(self) -> bool:
        return self.family in (ChordFamily.MINOR, ChordFamily.DIMINISHED)

    def with_bass(self, bass: int | None) -> Chord:
        return replace(self, bass=None if bass == self.root else bass)

    def format(self, key: Key | None = None, spelling: Spelling = Spelling.DEFAULT) -> str:
        def spell(pc: int) -> str:
            return key.spell(pc) if key is not None else note_name(pc, spelling)

        text = spell(self.root) + self.suffix
        if self.bass is not None and self.bass != self.root:
            text += "/" + spell(self.bass)
        return text


def suffix_family(suffix: str) -> ChordFamily:
    s = suffix.replace("(", "").replace(")", "")
    if s.startswith(("dim", "°", "o", "ø")) or "m7b5" in s or "min7b5" in s:
        return ChordFamily.DIMINISHED
    if s.startswith(("aug", "+")):
        return ChordFamily.AUGMENTED
    if s.startswith(("m", "min", "-")) and not s.startswith(("maj", "M")):
        return ChordFamily.MINOR
    if s == "5":
        return ChordFamily.POWER
    if s.startswith("sus") or s.startswith("7sus"):
        return ChordFamily.SUSPENDED
    return ChordFamily.MAJOR


def is_no_chord(symbol: str) -> bool:
    return symbol.strip().upper() in {"N", "N.C.", "NC", "X"}


def parse_chord(symbol: str) -> Chord:
    """Parse a chord symbol such as ``C``, ``F#m7``, ``Bbmaj7``, ``G/B`` or ``E♭sus4``."""
    text = symbol.strip()
    match = _CHORD_RE.match(text)
    if not match:
        raise ChordParseError(f"Not a chord symbol: {symbol!r}")
    root_text, suffix, bass_text = match.groups()
    try:
        root = parse_note(root_text)
        bass = parse_note(bass_text) if bass_text else None
    except NoteParseError as exc:
        raise ChordParseError(str(exc)) from exc
    return Chord(root=root, suffix=_normalise_suffix(suffix), bass=bass)


_SUFFIX_ALIASES = {
    "maj": "",
    "M": "",
    "major": "",
    "min": "m",
    "minor": "m",
    "-": "m",
    "M7": "maj7",
    "Maj7": "maj7",
    "Δ": "maj7",
    "Δ7": "maj7",
    "min7": "m7",
    "-7": "m7",
    "°": "dim",
    "o": "dim",
    "°7": "dim7",
    "o7": "dim7",
    "ø": "m7b5",
    "ø7": "m7b5",
    "min7b5": "m7b5",
    "+": "aug",
    "sus": "sus4",
    "add2": "add9",
}


def _normalise_suffix(suffix: str) -> str:
    return _SUFFIX_ALIASES.get(suffix, suffix)


def chord_pitch_classes(chord: Chord) -> tuple[int, ...]:
    """Pitch classes for canonical suffixes; falls back to the family triad."""
    intervals = QUALITY_INTERVALS.get(chord.suffix)
    if intervals is None:
        intervals = {
            ChordFamily.MINOR: QUALITY_INTERVALS["m"],
            ChordFamily.DIMINISHED: QUALITY_INTERVALS["dim"],
            ChordFamily.AUGMENTED: QUALITY_INTERVALS["aug"],
            ChordFamily.SUSPENDED: QUALITY_INTERVALS["sus4"],
            ChordFamily.POWER: (0, 7),
        }.get(chord.family, QUALITY_INTERVALS[""])
    return tuple((chord.root + i) % 12 for i in intervals)
