"""Domain errors with stable codes and user-safe messages.

Every error raised to the API layer carries a machine-readable ``code`` (for n8n and
other automations) and a friendly ``message``. Internal details never reach clients.
"""

from __future__ import annotations


class ChordAnalyzerError(Exception):
    code = "internal_error"
    status_code = 500
    message = "Something went wrong while analyzing this audio. Please try again."

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        if message:
            self.message = message
        if code:
            self.code = code
        super().__init__(self.message)


class UnsupportedFormatError(ChordAnalyzerError):
    code = "unsupported_format"
    status_code = 415
    message = "This file type is not supported. Please upload MP3, WAV, M4A, AAC, FLAC or OGG."


class FileTooLargeError(ChordAnalyzerError):
    code = "file_too_large"
    status_code = 413
    message = "This file is too large."


class CorruptedAudioError(ChordAnalyzerError):
    code = "corrupted_audio"
    status_code = 422
    message = "We could not read this audio file. It may be corrupted or incomplete."


class AudioTooShortError(ChordAnalyzerError):
    code = "audio_too_short"
    status_code = 422
    message = "This audio is too short to analyze."


class AudioTooLongError(ChordAnalyzerError):
    code = "audio_too_long"
    status_code = 422
    message = "This audio is too long to analyze."


class SilentAudioError(ChordAnalyzerError):
    code = "silent_audio"
    status_code = 422
    message = "This audio appears to be silent."


class InsufficientHarmonicContentError(ChordAnalyzerError):
    code = "insufficient_harmonic_content"
    status_code = 422
    message = "We could not detect enough harmonic content from this audio."


class FFmpegError(ChordAnalyzerError):
    code = "conversion_failed"
    status_code = 422
    message = "We could not convert this audio file. It may be corrupted or use an unusual codec."


class DependencyMissingError(ChordAnalyzerError):
    code = "dependency_missing"
    status_code = 503
    message = "The audio engine is not available on this server (FFmpeg missing)."


class AnalysisTimeoutError(ChordAnalyzerError):
    code = "analysis_timeout"
    status_code = 504
    message = "Analysis took too long and was stopped. Try a shorter audio file."


class QueueFullError(ChordAnalyzerError):
    code = "queue_full"
    status_code = 503
    message = "The analyzer is busy right now. Please try again in a minute."


class JobNotFoundError(ChordAnalyzerError):
    code = "not_found"
    status_code = 404
    message = "Analysis not found."


class JobNotReadyError(ChordAnalyzerError):
    code = "not_ready"
    status_code = 409
    message = "This analysis is not finished yet."


class InvalidRequestError(ChordAnalyzerError):
    code = "invalid_request"
    status_code = 422
    message = "Invalid request."


class RateLimitedError(ChordAnalyzerError):
    code = "rate_limited"
    status_code = 429
    message = "Too many requests. Please slow down."


class UnauthorizedError(ChordAnalyzerError):
    code = "unauthorized"
    status_code = 401
    message = "A valid API key is required."
