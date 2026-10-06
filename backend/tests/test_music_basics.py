from __future__ import annotations

import pytest

from app.music.chords import ChordFamily, ChordParseError, parse_chord
from app.music.keys import (
    Key,
    KeyParseError,
    Mode,
    normalize_key_name,
    parse_key,
    semitones_between,
)
from app.music.notes import NoteParseError, parse_note


@pytest.mark.parametrize(
    ("name", "pc"),
    [("C", 0), ("C#", 1), ("Db", 1), ("E♭", 3), ("B#", 0), ("Cb", 11), ("f#", 6), ("Bbb", 9)],
)
def test_parse_note(name: str, pc: int) -> None:
    assert parse_note(name) == pc


def test_parse_note_rejects_garbage() -> None:
    with pytest.raises(NoteParseError):
        parse_note("H")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("C", "C Major"),
        ("c major", "C Major"),
        ("Am", "A Minor"),
        ("a minor", "A Minor"),
        ("F#m", "F# Minor"),
        ("Gb major", "F# Major"),
        ("D#m", "Eb Minor"),
        ("Bbmaj", "Bb Major"),
        ("Ab Minor", "G# Minor"),
        ("Eb", "Eb Major"),
    ],
)
def test_key_normalization(text: str, expected: str) -> None:
    assert normalize_key_name(text) == expected


def test_key_parse_errors() -> None:
    for bad in ["H major", "C dorian", ""]:
        with pytest.raises(KeyParseError):
            parse_key(bad)


def test_key_spelling_by_scale_degree() -> None:
    g_major = Key(7, Mode.MAJOR)
    assert g_major.spell(10) == "Bb"  # bIII in G is Bb, not A#
    assert g_major.spell(6) == "F#"
    b_major = Key(11, Mode.MAJOR)
    assert b_major.spell(3) == "D#"
    f_major = Key(5, Mode.MAJOR)
    assert f_major.spell(10) == "Bb"
    a_minor = Key(9, Mode.MINOR)
    assert a_minor.spell(8) == "G#"  # leading tone
    fsharp_major = Key(6, Mode.MAJOR)
    assert fsharp_major.spell(5) == "F"  # avoid E#


def test_relative_and_semitones() -> None:
    assert Key(0, Mode.MAJOR).relative == Key(9, Mode.MINOR)
    assert semitones_between(Key(0, Mode.MAJOR), Key(2, Mode.MAJOR)) == 2
    assert semitones_between(Key(0, Mode.MAJOR), Key(10, Mode.MAJOR)) == -2
    assert semitones_between(Key(0, Mode.MAJOR), Key(6, Mode.MAJOR)) == 6


@pytest.mark.parametrize(
    ("symbol", "root", "suffix", "bass", "family"),
    [
        ("C", 0, "", None, ChordFamily.MAJOR),
        ("F#m7", 6, "m7", None, ChordFamily.MINOR),
        ("Bbmaj7", 10, "maj7", None, ChordFamily.MAJOR),
        ("G/B", 7, "", 11, ChordFamily.MAJOR),
        ("Esus4", 4, "sus4", None, ChordFamily.SUSPENDED),
        ("Bdim", 11, "dim", None, ChordFamily.DIMINISHED),
        ("Bm7b5", 11, "m7b5", None, ChordFamily.DIMINISHED),
        ("Caug", 0, "aug", None, ChordFamily.AUGMENTED),
        ("Amin", 9, "m", None, ChordFamily.MINOR),
        ("CM7", 0, "maj7", None, ChordFamily.MAJOR),
        ("D7sus4", 2, "7sus4", None, ChordFamily.SUSPENDED),
    ],
)
def test_parse_chord(
    symbol: str, root: int, suffix: str, bass: int | None, family: ChordFamily
) -> None:
    chord = parse_chord(symbol)
    assert (chord.root, chord.suffix, chord.bass, chord.family) == (root, suffix, bass, family)


def test_parse_chord_errors() -> None:
    for bad in ["", "H7", "c", "C/X"]:
        with pytest.raises(ChordParseError):
            parse_chord(bad)
