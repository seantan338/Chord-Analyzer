"""Markdown chord sheet (for Notion, Google Docs import, GitHub, Obsidian ...)."""

from __future__ import annotations

from app.exporters.chord_sheet import build_sheet
from app.exporters.common import DISCLAIMER, format_time
from app.exporters.text import MIN_CELL
from app.schemas.analysis import AnalysisResult


def render_markdown(result: AnalysisResult, mode: str) -> str:
    sheet = build_sheet(result, "beginner" if mode == "beginner" else "original")
    cells = [cell for section in sheet.sections for line in section.lines for cell in line]
    width = max([MIN_CELL, *(len(c) for c in cells)])

    out = [
        f"# {sheet.title}",
        "",
        "| Key | Tempo | Time signature |",
        "| --- | --- | --- |",
        f"| {sheet.key} | {round(sheet.bpm)} BPM | {sheet.time_signature} |",
        "",
    ]
    out += [f"> {note}" for note in sheet.notes]
    if sheet.notes:
        out.append("")
    for section in sheet.sections:
        out += [f"## {section.name} `{format_time(section.start)}`", "", "```text"]
        out += ["| " + " | ".join(c.ljust(width) for c in line) + " |" for line in section.lines]
        out += ["```", ""]

    chords = result.beginner_chords if mode == "beginner" else result.chords
    out += [
        "<details>",
        "<summary>Chord timeline with timestamps</summary>",
        "",
        "| Time | Chord | Confidence |",
        "| --- | --- | --- |",
    ]
    out += [
        f"| {format_time(c.start)} | {c.chord} | {c.confidence_level} |"
        for c in chords
        if c.chord != "N"
    ]
    out += ["", "</details>", "", f"_{DISCLAIMER}_"]
    return "\n".join(out) + "\n"
