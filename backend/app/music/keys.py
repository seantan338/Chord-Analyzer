"""Musical keys: parsing, normalisation and key-aware note spelling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.music.notes import (
    LETTER_PITCH,
    LETTERS,
    NoteParseError,
    Spelling,
    note_name,
    parse_note,
    split_note_name,
)

# Conventional tonic names (fewest accidentals; F# preferred over Gb for majors).
MAJOR_TONIC_NAMES = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
MINOR_TONIC_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B")

_S, _F, _D = Spelling.SHARP, Spelling.FLAT, Spelling.DEFAULT
_MAJOR_SPELLING = (_D, _F, _S, _F, _S, _F, _S, _S, _F, _S, _F, _S)
_MINOR_SPELLING = (_F, _S, _F, _F, _S, _F, _S, _F, _S, _D, _F, _S)

# Semitones above the tonic -> number of letter steps (scale-degree spelling).
# e.g. 3 semitones = flat third (2 letters up), 6 semitones = sharp fourth.
_DEGREE_LETTER_STEPS = (0, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6)
_AWKWARD_NAMES = {"E#", "B#", "Cb", "Fb"}

_KEY_RE = re.compile(r"^\s*([A-Ga-g][#b♯♭]?)\s*([A-Za-z]*)\s*$")
_MAJOR_WORDS = {"", "maj", "major"}
_MINOR_WORDS = {"min", "minor"}


class Mode(str, Enum):
    MAJOR = "major"
    MINOR = "minor"


class KeyParseError(ValueError):
    pass


@dataclass(frozen=True)
class Key:
    tonic: int  # pitch class 0-11
    mode: Mode

    @property
    def tonic_name(self) -> str:
        names = MAJOR_TONIC_NAMES if self.mode is Mode.MAJOR else MINOR_TONIC_NAMES
        return names[self.tonic % 12]

    @property
    def name(self) -> str:
        """Canonical display name, e.g. ``"Eb Major"`` or ``"F# Minor"``."""
        return f"{self.tonic_name} {self.mode.value.capitalize()}"

    @property
    def short_name(self) -> str:
        """Chord-style key name, e.g. ``"Eb"`` or ``"F#m"``."""
        return self.tonic_name + ("m" if self.mode is Mode.MINOR else "")

    @property
    def spelling(self) -> Spelling:
        table = _MAJOR_SPELLING if self.mode is Mode.MAJOR else _MINOR_SPELLING
        return table[self.tonic % 12]

    @property
    def relative(self) -> Key:
        if self.mode is Mode.MAJOR:
            return Key((self.tonic + 9) % 12, Mode.MINOR)
        return Key((self.tonic + 3) % 12, Mode.MAJOR)

    def transposed(self, semitones: int) -> Key:
        return Key((self.tonic + semitones) % 12, self.mode)

    def spell(self, pitch_class: int) -> str:
        """Spell a pitch class by its scale degree in this key (Bb in G major, not A#).

        Falls back to the key's accidental preference when degree spelling would need
        double accidentals or awkward names such as E# or Cb.
        """
        interval = (pitch_class - self.tonic) % 12
        tonic_letter, _ = split_note_name(self.tonic_name)
        letter_index = (LETTERS.index(tonic_letter) + _DEGREE_LETTER_STEPS[interval]) % 7
        letter = LETTERS[letter_index]
        offset = (pitch_class - LETTER_PITCH[letter] + 6) % 12 - 6
        if abs(offset) <= 1:
            candidate = letter + {-1: "b", 0: "", 1: "#"}[offset]
            if candidate not in _AWKWARD_NAMES:
                return candidate
        return note_name(pitch_class, self.spelling)


def parse_key(text: str) -> Key:
    """Parse ``"C Major"``, ``"c minor"``, ``"F#m"``, ``"Bbmaj"``, ``"A"`` (major) etc."""
    match = _KEY_RE.match(text.replace("-", " "))
    if not match:
        raise KeyParseError(f"Not a key: {text!r}")
    tonic_text, mode_text = match.groups()
    try:
        tonic = parse_note(tonic_text)
    except NoteParseError as exc:
        raise KeyParseError(str(exc)) from exc
    if mode_text == "m" or mode_text.lower() in _MINOR_WORDS:
        return Key(tonic, Mode.MINOR)
    if mode_text == "M" or mode_text.lower() in _MAJOR_WORDS:
        return Key(tonic, Mode.MAJOR)
    raise KeyParseError(f"Unknown mode in key: {text!r}")


def normalize_key_name(text: str) -> str:
    return parse_key(text).name


def semitones_between(source: Key, target: Key) -> int:
    """Smallest signed shift from ``source`` tonic to ``target`` tonic, in [-5, +6]."""
    shift = (target.tonic - source.tonic) % 12
    return shift - 12 if shift > 6 else shift


def all_keys(mode: Mode) -> list[Key]:
    return [Key(pc, mode) for pc in range(12)]
