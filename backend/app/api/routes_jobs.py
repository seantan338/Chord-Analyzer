"""Analysis job endpoints.

POST /api/analyze                 multipart "file" -> {job_id}
GET  /api/jobs/{job_id}           status + current stage
GET  /api/jobs/{job_id}/result    full analysis JSON
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from app.api.deps import get_service, rate_limited, require_api_key
from app.core.errors import ChordAnalyzerError
from app.models.job import PROGRESS_STAGES, STAGE_LABELS, Job, JobStatus
from app.schemas.analysis import AnalysisResult
from app.schemas.jobs import (
    ErrorInfo,
    ErrorResponse,
    JobCreated,
    JobLinks,
    JobState,
    JobSummary,
    StageInfo,
)
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api", tags=["analysis"], dependencies=[Depends(require_api_key)])

WAIT_POLL_SECONDS = 0.5
_ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorResponse} for code in (401, 404, 409, 413, 415, 422, 429, 503)
}


def links(job_id: str) -> JobLinks:
    base = f"/api/jobs/{job_id}"
    return JobLinks(
        status=base, result=f"{base}/result", export_markdown=f"{base}/export?format=markdown"
    )


def stage_list(job: Job) -> list[StageInfo]:
    if job.status is JobStatus.COMPLETED:
        current = len(PROGRESS_STAGES)
    elif job.stage in PROGRESS_STAGES:
        current = PROGRESS_STAGES.index(job.stage)
    else:
        current = -1  # queued, or failed before a stage was recorded
    infos = []
    for i, stage in enumerate(PROGRESS_STAGES):
        state = "done" if i < current else "active" if i == current else "pending"
        if job.status is JobStatus.FAILED and state == "active":
            state = "failed"
        infos.append(StageInfo(id=stage, label=STAGE_LABELS[stage], state=state))
    return infos


def job_state(job: Job) -> JobState:
    error = (
        ErrorInfo(code=job.error_code or "analysis_failed", message=job.error_message or "")
        if job.status is JobStatus.FAILED
        else None
    )
    return JobState(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        stage_label=STAGE_LABELS[job.stage],
        stages=stage_list(job),
        filename=job.filename,
        file_size=job.file_size,
        created_at=job.created_at,
        updated_at=job.updated_at,
        summary=JobSummary(duration=job.duration, key=job.key, bpm=job.bpm),
        error=error,
        links=links(job.id),
    )


@router.post(
    "/analyze",
    status_code=202,
    response_model=JobCreated,
    responses=_ERRORS,
    dependencies=[Depends(rate_limited("analyze"))],
    summary="Upload an audio file for analysis",
)
async def analyze(
    response: Response,
    file: UploadFile = File(description="MP3, WAV, M4A, AAC, FLAC or OGG"),
    wait: int = Query(
        0,
        ge=0,
        le=300,
        description="Seconds to wait for completion; if it finishes in time the full result "
        "is included (handy for n8n / single-request integrations).",
    ),
    service: AnalysisService = Depends(get_service),
) -> JobCreated:
    submission = await service.submit(file, file.filename, file.content_type)
    job = submission.job
    deadline = time.monotonic() + wait
    while job.status in (JobStatus.QUEUED, JobStatus.PROCESSING) and time.monotonic() < deadline:
        await asyncio.sleep(WAIT_POLL_SECONDS)
        job = service.get_job(job.id)

    result = None
    if job.status is JobStatus.COMPLETED:
        response.status_code = 200
        if wait or submission.cached:
            result = service.get_result(job.id)
    elif job.status is JobStatus.FAILED and wait:
        error = ChordAnalyzerError(job.error_message)
        error.code = job.error_code or error.code
        error.status_code = 422
        raise error
    return JobCreated(
        job_id=job.id,
        status=job.status,
        cached=submission.cached,
        links=links(job.id),
        result=result,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobState,
    responses=_ERRORS,
    dependencies=[Depends(rate_limited("read"))],
    summary="Job status and current processing stage",
)
async def get_job(job_id: str, service: AnalysisService = Depends(get_service)) -> JobState:
    return job_state(service.get_job(job_id))


@router.get(
    "/jobs/{job_id}/result",
    response_model=AnalysisResult,
    responses=_ERRORS,
    dependencies=[Depends(rate_limited("read"))],
    summary="Full analysis result",
)
async def get_result(
    job_id: str, service: AnalysisService = Depends(get_service)
) -> AnalysisResult:
    return service.get_result(job_id)
