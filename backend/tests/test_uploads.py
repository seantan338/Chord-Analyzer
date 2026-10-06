from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.audio.formats import AAC, FLAC, MP3, MP4, OGG, WAV, sniff_file, sniff_format
from app.core.errors import FileTooLargeError, UnsupportedFormatError
from app.services.uploads import UploadStore, sanitize_filename, validate_declared_type


class _Stream:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self, size: int = -1) -> bytes:
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk


@pytest.mark.parametrize(
    ("header", "fmt"),
    [
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", WAV),
        (b"fLaC\x00\x00\x00\x22", FLAC),
        (b"OggS\x00\x02", OGG),
        (b"\x00\x00\x00\x20ftypM4A ", MP4),
        (b"\xff\xfb\x90\x64", MP3),
        (b"\xff\xf1\x50\x80", AAC),
    ],
)
def test_sniff_known_formats(header: bytes, fmt: object) -> None:
    assert sniff_format(header) == fmt


@pytest.mark.parametrize(
    "header",
    [b"#EXTM3U\n#EXT-X-VERSION", b"ffconcat version 1.0", b"<html>", b"MZ\x90\x00", b""],
)
def test_sniff_rejects_non_audio(header: bytes) -> None:
    assert sniff_format(header) is None


def test_sniff_id3_tagged_mp3(tmp_path: Path) -> None:
    tag = b"ID3\x04\x00\x00\x00\x00\x00\x0a" + b"\x00" * 10
    path = tmp_path / "x.mp3"
    path.write_bytes(tag + b"\xff\xfb\x90\x64" + b"\x00" * 100)
    assert sniff_file(path) == MP3


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("song.mp3", "song.mp3"),
        ("../../etc/passwd.mp3", "passwd.mp3"),
        ("C:\\Users\\me\\My Song.wav", "My Song.wav"),
        ("bad\x00name\x1f.flac", "badname.flac"),
        ("", "audio"),
        (None, "audio"),
        ("a" * 300 + ".mp3", "a" * 116 + ".mp3"),
    ],
)
def test_sanitize_filename(raw: str | None, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_declared_type_validation() -> None:
    validate_declared_type("x.mp3", "audio/mpeg")
    validate_declared_type("x.m4a", "audio/x-m4a")
    validate_declared_type("x.wav", "application/octet-stream")
    with pytest.raises(UnsupportedFormatError):
        validate_declared_type("x.exe", "audio/mpeg")
    with pytest.raises(UnsupportedFormatError):
        validate_declared_type("x.mp3", "text/html")


def test_upload_store_enforces_size_and_cleans_up(tmp_path: Path) -> None:
    store = UploadStore(tmp_path, max_bytes=1000)
    store.prepare()
    with pytest.raises(FileTooLargeError):
        asyncio.run(
            store.save(
                _Stream(b"RIFF" + b"\x00" * 2000),
                job_id="a" * 32,
                filename="x.wav",
                content_type=None,
            )
        )
    assert not (tmp_path / ("a" * 32)).exists()


def test_upload_store_rejects_disguised_file(tmp_path: Path) -> None:
    store = UploadStore(tmp_path, max_bytes=10_000)
    store.prepare()
    with pytest.raises(UnsupportedFormatError):
        asyncio.run(
            store.save(
                _Stream(b"#EXTM3U\nhttp://evil/x.ts\n"),
                job_id="b" * 32,
                filename="song.mp3",
                content_type="audio/mpeg",
            )
        )
    assert not (tmp_path / ("b" * 32)).exists()


def test_upload_store_saves_with_uuid_name(tmp_path: Path) -> None:
    store = UploadStore(tmp_path, max_bytes=10_000)
    store.prepare()
    data = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100
    saved = asyncio.run(
        store.save(
            _Stream(data), job_id="c" * 32, filename="../My Song.wav", content_type="audio/wav"
        )
    )
    assert saved.fmt == WAV
    assert saved.display_name == "My Song.wav"
    assert saved.path.parent == tmp_path / ("c" * 32)
    assert saved.path.name.endswith(".upload") and "Song" not in saved.path.name
    assert saved.size == len(data)
    store.discard(saved)
    assert not saved.work_dir.exists()
