"""Audio container detection by magic bytes.

The detected format decides which FFmpeg demuxer is *forced* when decoding. Forcing the
demuxer means a file can never be interpreted as a playlist (HLS, concat) that would
make FFmpeg open other files or URLs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioFormat:
    name: str
    demuxer: str
    extensions: tuple[str, ...]


MP3 = AudioFormat("mp3", "mp3", (".mp3",))
WAV = AudioFormat("wav", "wav", (".wav", ".wave"))
FLAC = AudioFormat("flac", "flac", (".flac",))
OGG = AudioFormat("ogg", "ogg", (".ogg", ".oga"))
MP4 = AudioFormat("m4a", "mov", (".m4a", ".mp4", ".aac"))
AAC = AudioFormat("aac", "aac", (".aac",))

SUPPORTED_FORMATS = (MP3, WAV, FLAC, OGG, MP4, AAC)
ALLOWED_EXTENSIONS = frozenset(ext for fmt in SUPPORTED_FORMATS for ext in fmt.extensions)
SNIFF_BYTES = 64


def _is_mpeg_audio_frame(header: bytes) -> bool:
    # 11-bit frame sync, MPEG layer bits != 00 (00 = ADTS AAC)
    return (
        len(header) >= 2
        and header[0] == 0xFF
        and (header[1] & 0xE0) == 0xE0
        and (header[1] & 0x06) != 0
    )


def _is_adts_frame(header: bytes) -> bool:
    return len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xF6) == 0xF0


def _id3_size(header: bytes) -> int:
    """Total size of a leading ID3v2 tag (syncsafe integer), or 0."""
    if len(header) < 10 or header[:3] != b"ID3":
        return 0
    size = 0
    for byte in header[6:10]:
        size = (size << 7) | (byte & 0x7F)
    footer = 10 if header[5] & 0x10 else 0
    return 10 + size + footer


def sniff_format(header: bytes, after_id3: bytes | None = None) -> AudioFormat | None:
    """Detect the container from the first bytes of a file.

    ``after_id3`` are the bytes following an ID3 tag, used to tell MP3 from ADTS AAC.
    """
    if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return WAV
    if header[:4] == b"fLaC":
        return FLAC
    if header[:4] == b"OggS":
        return OGG
    if header[4:8] == b"ftyp":
        return MP4
    if header[:3] == b"ID3":
        if after_id3 is not None and _is_adts_frame(after_id3):
            return AAC
        return MP3
    if _is_adts_frame(header):
        return AAC
    if _is_mpeg_audio_frame(header):
        return MP3
    return None


def sniff_file(path: Path) -> AudioFormat | None:
    with path.open("rb") as fh:
        header = fh.read(SNIFF_BYTES)
        after_id3 = None
        tag_size = _id3_size(header)
        if tag_size:
            fh.seek(tag_size)
            after_id3 = fh.read(4)
    return sniff_format(header, after_id3)
