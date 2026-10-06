"""Job API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.job import JobStatus, Stage
from app.schemas.analysis import AnalysisResult


class ErrorInfo(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorInfo


class JobLinks(BaseModel):
    status: str
    result: str
    export_markdown: str


class JobCreated(BaseModel):
    job_id: str
    status: JobStatus
    cached: bool = Field(description="True when an identical file was analysed before")
    links: JobLinks
    result: AnalysisResult | None = Field(
        default=None, description="Included when the job is already complete (cache hit or ?wait=)"
    )


class StageInfo(BaseModel):
    id: Stage
    label: str
    state: Literal["done", "active", "pending", "failed"]


class JobSummary(BaseModel):
    duration: float | None
    key: str | None
    bpm: float | None


class JobState(BaseModel):
    job_id: str
    status: JobStatus
    stage: Stage
    stage_label: str
    stages: list[StageInfo]
    filename: str
    file_size: int
    created_at: datetime
    updated_at: datetime
    summary: JobSummary
    error: ErrorInfo | None = None
    links: JobLinks


class ServiceLimits(BaseModel):
    max_upload_mb: int
    allowed_extensions: list[str]
    min_duration_seconds: float
    max_duration_seconds: float


class HealthResponse(BaseModel):
    status: str
    version: str
    ffmpeg: bool
    limits: ServiceLimits
