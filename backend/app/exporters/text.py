"""Plain-text chord sheet (monospace, copy/paste friendly)."""

from __future__ import annotations

from app.exporters.chord_sheet import ChordSheet, build_sheet
from app.exporters.common import DISCLAIMER, format_time, header_line
from app.schemas.analysis import AnalysisResult

MIN_CELL = 6


def render_sheet_text(sheet: ChordSheet) -> str:
    cells = [cell for section in sheet.sections for line in section.lines for cell in line]
    width = max([MIN_CELL, *(len(c) for c in cells)])
    out = [sheet.title, header_line(sheet), *sheet.notes, ""]
    for section in sheet.sections:
        out.append(f"[{section.name}] {format_time(section.start)}")
        for line in section.lines:
            out.append("| " + " | ".join(cell.ljust(width) for cell in line) + " |")
        out.append("")
    out.append(DISCLAIMER)
    return "\n".join(out) + "\n"


def render_text(result: AnalysisResult, mode: str) -> str:
    return render_sheet_text(build_sheet(result, "beginner" if mode == "beginner" else "original"))
