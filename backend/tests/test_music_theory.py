"""Transposition, simplification and capo suggestion (pure music-theory functions)."""

from __future__ import annotations

import pytest

from app.music.capo import suggest_capo
from app.music.keys import Key, Mode, parse_key
from app.music.simplifier import simplify_symbol
from app.music.transpose import normalize_semitones, transpose_progression, transpose_symbol


@pytest.mark.parametrize(
    ("chord", "semitones", "expected"),
    [
        ("C", 2, "D"),
        ("Am", 2, "Bm"),
        ("G/B", 2, "A/C#"),
        ("Bb", 2, "C"),
        ("F#m7", -2, "Em7"),
        ("Cmaj7", 1, "C#maj7"),
        ("Ebsus4", -1, "Dsus4"),
        ("Bdim", 1, "Cdim"),
        ("A7", 12, "A7"),
        ("E", -13, "Eb"),
        ("Dm7b5", 3, "Fm7b5"),
        ("N", 5, "N"),
    ],
)
def test_transpose_symbol(chord: str, semitones: int, expected: str) -> None:
    assert transpose_symbol(chord, semitones) == expected


def test_transpose_progression_to_target_key() -> None:
    target = parse_key("D Major")
    assert transpose_progression(["C", "G", "Am", "F"], 2, target) == ["D", "A", "Bm", "G"]


@pytest.mark.parametrize(
    ("chord", "semitones", "key", "expected"),
    [
        ("A", 1, "F Major", "Bb"),  # flat key -> flat spelling
        ("A", 1, "B Major", "A#"),  # sharp key -> sharp spelling
        ("G", 3, "G Major", "Bb"),  # bIII in G is Bb, not A#
        ("C#m", 0, "E Major", "C#m"),
        ("Db", 0, "Ab Major", "Db"),
        ("G/B", 5, "C Major", "C/E"),
    ],
)
def test_transpose_spelling_follows_key(
    chord: str, semitones: int, key: str, expected: str
) -> None:
    assert transpose_symbol(chord, semitones, parse_key(key)) == expected


def test_unknown_symbols_pass_through() -> None:
    assert transpose_symbol("???", 2) == "???"
    assert simplify_symbol("???") == "???"


@pytest.mark.parametrize("value,expected", [(0, 0), (2, 2), (7, -5), (11, -1), (-7, 5), (12, 0)])
def test_normalize_semitones(value: int, expected: int) -> None:
    assert normalize_semitones(value) == expected


@pytest.mark.parametrize(
    ("chord", "expected"),
    [
        ("Cmaj7", "C"),
        ("Am7", "Am"),
        ("Fadd9", "F"),
        ("Gsus4", "G"),
        ("G/B", "G"),
        ("D7", "D"),
        ("Bdim", "Bm"),
        ("F#m7b5", "F#m"),
        ("Caug", "C"),
        ("E5", "E"),
        ("Ebm9", "Ebm"),
        ("Bbmaj7/D", "Bb"),
        ("N", "N"),
    ],
)
def test_simplify(chord: str, expected: str) -> None:
    assert simplify_symbol(chord) == expected


def _timed(chords: list[str]) -> list[tuple[str, float]]:
    return [(c, 4.0) for c in chords]


def test_capo_for_eb_major_suggests_c_shapes() -> None:
    advice = suggest_capo(Key(3, Mode.MAJOR), _timed(["Eb", "Bb", "Cm", "Ab"] * 4))
    capos = {o.capo: o for o in advice.options}
    assert 3 in capos
    assert capos[3].play_key.name == "C Major"
    assert capos[3].play_chords == ["C", "G", "Am", "F"]
    assert 1 <= len(advice.options) <= 3
    assert advice.options[0].capo == 3
    assert advice.options[0].playability >= advice.original_playability


def test_no_capo_for_easy_keys() -> None:
    advice = suggest_capo(Key(7, Mode.MAJOR), _timed(["G", "D", "Em", "C"]))
    assert advice.options == []
    assert "no capo needed" in advice.note


def test_capo_minor_key() -> None:
    advice = suggest_capo(Key(5, Mode.MINOR), _timed(["Fm", "Db", "Ab", "Eb"]))
    assert advice.options, advice.note
    best = advice.options[0]
    assert best.play_key.mode is Mode.MINOR
    assert all("b" not in chord for chord in best.play_chords[:2])


def test_capo_ignores_no_chord() -> None:
    advice = suggest_capo(Key(0, Mode.MAJOR), [("N", 10.0)])
    assert advice.options == []
