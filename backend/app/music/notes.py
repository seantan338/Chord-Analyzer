"""Pitch classes and note spelling. Pure functions, no audio dependencies."""

from __future__ import annotations

import re
from enum import Enum

LETTERS = ("C", "D", "E", "F", "G", "A", "B")
LETTER_PITCH = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
# Most common chord-chart spelling when no key context is known.
DEFAULT_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")

_NOTE_RE = re.compile(r"^([A-Ga-g])([#b♯♭]{0,2})$")
_ACCIDENTAL_VALUE = {"#": 1, "♯": 1, "b": -1, "♭": -1}


class Spelling(str, Enum):
    SHARP = "sharp"
    FLAT = "flat"
    DEFAULT = "default"


_NAME_TABLES = {
    Spelling.SHARP: SHARP_NAMES,
    Spelling.FLAT: FLAT_NAMES,
    Spelling.DEFAULT: DEFAULT_NAMES,
}


class NoteParseError(ValueError):
    pass


def parse_note(name: str) -> int:
    """Return the pitch class (0-11, C=0) of a note name such as ``F#``, ``Bb`` or ``E♭``."""
    match = _NOTE_RE.match(name.strip())
    if not match:
        raise NoteParseError(f"Not a note name: {name!r}")
    letter, accidentals = match.groups()
    offset = sum(_ACCIDENTAL_VALUE[a] for a in accidentals)
    return (LETTER_PITCH[letter.upper()] + offset) % 12


def note_name(pitch_class: int, spelling: Spelling = Spelling.DEFAULT) -> str:
    return _NAME_TABLES[spelling][pitch_class % 12]


def split_note_name(name: str) -> tuple[str, int]:
    """Split a canonical note name into (letter, accidental offset)."""
    letter = name[0].upper()
    offset = sum(_ACCIDENTAL_VALUE[a] for a in name[1:])
    return letter, offset
