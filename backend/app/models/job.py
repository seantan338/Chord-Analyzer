"""Job domain model shared by the API, the repository and the worker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Stage(str, Enum):
    """Processing stages in execution order. Progress is reported per stage, not %."""

    QUEUED = "queued"
    CONVERTING = "converting"
    HARMONIC_FEATURES = "harmonic_features"
    TEMPO = "tempo"
    KEY = "key"
    CHORDS = "chords"
    STRUCTURE = "structure"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    FAILED = "failed"


STAGE_LABELS: dict[Stage, str] = {
    Stage.QUEUED: "Waiting in queue",
    Stage.CONVERTING: "Converting audio",
    Stage.HARMONIC_FEATURES: "Extracting harmonic features",
    Stage.TEMPO: "Detecting tempo",
    Stage.KEY: "Detecting key",
    Stage.CHORDS: "Detecting chords",
    Stage.STRUCTURE: "Segmenting song structure",
    Stage.FINALIZING: "Generating chord sheet",
    Stage.COMPLETE: "Complete",
    Stage.FAILED: "Failed",
}

PROGRESS_STAGES: tuple[Stage, ...] = (
    Stage.CONVERTING,
    Stage.HARMONIC_FEATURES,
    Stage.TEMPO,
    Stage.KEY,
    Stage.CHORDS,
    Stage.STRUCTURE,
    Stage.FINALIZING,
)


@dataclass(frozen=True)
class Job:
    id: str
    filename: str
    file_size: int
    file_hash: str
    status: JobStatus
    stage: Stage
    created_at: datetime
    updated_at: datetime
    analyzer_version: str
    duration: float | None = None
    key: str | None = None
    bpm: float | None = None
    error_code: str | None = None
    error_message: str | None = None
    result_json: str | None = None
