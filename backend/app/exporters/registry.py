"""Export format registry.

Adding a format (e.g. PDF, MusicXML) = write a ``render_<format>(result, mode)`` function
returning ``str`` or ``bytes`` and register it here; the API endpoint picks it up.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.core.errors import InvalidRequestError
from app.exporters.markdown import render_markdown
from app.exporters.text import render_text
from app.schemas.analysis import AnalysisResult

Renderer = Callable[[AnalysisResult, str], str | bytes]


def render_json(result: AnalysisResult, mode: str) -> str:
    return result.model_dump_json(indent=2)


@dataclass(frozen=True)
class ExportFormat:
    name: str
    media_type: str
    extension: str
    render: Renderer


FORMATS: dict[str, ExportFormat] = {
    "txt": ExportFormat("txt", "text/plain; charset=utf-8", ".txt", render_text),
    "markdown": ExportFormat("markdown", "text/markdown; charset=utf-8", ".md", render_markdown),
    "json": ExportFormat("json", "application/json", ".json", render_json),
}
ALIASES = {"text": "txt", "md": "markdown"}


def get_format(name: str) -> ExportFormat:
    key = ALIASES.get(name.lower(), name.lower())
    if key not in FORMATS:
        options = ", ".join(sorted(FORMATS))
        raise InvalidRequestError(f"Unknown export format {name!r}. Use one of: {options}.")
    return FORMATS[key]
