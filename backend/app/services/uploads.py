"""Upload validation and temporary file handling.

* Files are streamed to ``<temp_root>/<job_id>/<uuid>.upload``; the client's filename is
  never used for paths (only shown, after sanitising).
* Size is enforced while streaming; the content type is checked by magic bytes, not by
  the (client-controlled) MIME header; FFmpeg later decodes with a forced demuxer.
* Temp directories are removed after analysis and swept after a TTL as a safety net.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Protocol

from app.audio.formats import ALLOWED_EXTENSIONS, AudioFormat, sniff_file
from app.core.errors import FileTooLargeError, InvalidRequestError, UnsupportedFormatError

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024
MAX_DISPLAY_NAME = 120
_ACCEPTED_MIME_PREFIXES = ("audio/",)
_ACCEPTED_MIME_EXACT = {"application/octet-stream", "video/mp4", "application/ogg", ""}


class AsyncReadable(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True)
class StoredUpload:
    work_dir: Path
    path: Path
    size: int
    sha256: str
    fmt: AudioFormat
    display_name: str


def sanitize_filename(raw: str | None) -> str:
    """Display-safe name: no directories, control characters or overly long names."""
    name = PurePath((raw or "").replace("\\", "/")).name
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", name).strip(" .")
    if len(name) > MAX_DISPLAY_NAME:
        stem, dot, ext = name.rpartition(".")
        name = (
            (stem[: MAX_DISPLAY_NAME - len(ext) - 1] + dot + ext)
            if dot
            else name[:MAX_DISPLAY_NAME]
        )
    return name or "audio"


def validate_declared_type(filename: str, content_type: str | None) -> None:
    extension = PurePath(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFormatError()
    mime = (content_type or "").split(";")[0].strip().lower()
    if not (mime.startswith(_ACCEPTED_MIME_PREFIXES) or mime in _ACCEPTED_MIME_EXACT):
        raise UnsupportedFormatError()


class UploadStore:
    def __init__(self, temp_root: Path, max_bytes: int) -> None:
        self.temp_root = temp_root
        self.max_bytes = max_bytes

    def prepare(self) -> None:
        self.temp_root.mkdir(parents=True, exist_ok=True, mode=0o700)

    async def save(
        self, stream: AsyncReadable, *, job_id: str, filename: str | None, content_type: str | None
    ) -> StoredUpload:
        display_name = sanitize_filename(filename)
        validate_declared_type(display_name, content_type)

        work_dir = self.temp_root / job_id
        work_dir.mkdir(parents=True, mode=0o700)
        path = work_dir / f"{uuid.uuid4().hex}.upload"
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("xb") as out:
                while chunk := await stream.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise FileTooLargeError(
                            "This file is too large. "
                            f"The limit is {self.max_bytes // (1024 * 1024)} MB."
                        )
                    digest.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise InvalidRequestError("The uploaded file is empty.")
            fmt = sniff_file(path)
            if fmt is None:
                raise UnsupportedFormatError()
        except BaseException:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise
        return StoredUpload(work_dir, path, size, digest.hexdigest(), fmt, display_name)

    def discard(self, upload: StoredUpload) -> None:
        shutil.rmtree(upload.work_dir, ignore_errors=True)

    def sweep(self, ttl_seconds: float) -> int:
        """Delete temp directories older than ``ttl_seconds``. Returns the number removed."""
        if not self.temp_root.exists():
            return 0
        cutoff = time.time() - ttl_seconds
        removed = 0
        for entry in self.temp_root.iterdir():
            try:
                if entry.is_dir() and entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
            except FileNotFoundError:
                continue
        if removed:
            logger.info("removed %d stale temp directories", removed)
        return removed
