"""Application service: submit uploads, track jobs, serve results."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from app.audio.loader import require_binary
from app.audio.pipeline import PipelineOptions
from app.core.config import ANALYZER_VERSION, Settings
from app.core.errors import (
    ChordAnalyzerError,
    JobNotFoundError,
    JobNotReadyError,
    QueueFullError,
)
from app.models.job import Job, JobStatus
from app.schemas.analysis import AnalysisResult
from app.services.job_repository import JobRepository
from app.services.job_runner import JobRunner
from app.services.uploads import AsyncReadable, UploadStore
from app.services.worker import JobSpec

_JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class JobFailedError(ChordAnalyzerError):
    code = "analysis_failed"
    status_code = 422


@dataclass(frozen=True)
class Submission:
    job: Job
    cached: bool


class AnalysisService:
    def __init__(
        self, settings: Settings, repo: JobRepository, runner: JobRunner, uploads: UploadStore
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.runner = runner
        self.uploads = uploads

    def _options(self) -> PipelineOptions:
        s = self.settings
        return PipelineOptions(
            min_duration=s.min_duration_seconds,
            max_duration=s.max_duration_seconds,
            ffmpeg_path=s.ffmpeg_path,
            ffprobe_path=s.ffprobe_path,
            chord_vocabulary=s.chord_vocabulary,
        )

    async def submit(
        self, stream: AsyncReadable, filename: str | None, content_type: str | None
    ) -> Submission:
        # Fail fast (503) instead of queueing a job that cannot run.
        require_binary(self.settings.ffmpeg_path)
        require_binary(self.settings.ffprobe_path)
        if self.repo.count_active() >= self.settings.max_queued_jobs:
            raise QueueFullError()
        job_id = uuid.uuid4().hex
        upload = await self.uploads.save(
            stream, job_id=job_id, filename=filename, content_type=content_type
        )

        cached = self.repo.find_completed_by_hash(upload.sha256, ANALYZER_VERSION)
        if cached is not None and cached.result_json:
            self.uploads.discard(upload)
            return Submission(
                self._clone_cached(job_id, cached, upload.display_name, upload.size), True
            )

        job = self.repo.create(
            job_id,
            filename=upload.display_name,
            file_size=upload.size,
            file_hash=upload.sha256,
            analyzer_version=ANALYZER_VERSION,
        )
        self.runner.submit(
            JobSpec(
                job_id=job_id,
                source_path=str(upload.path),
                work_dir=str(upload.work_dir),
                format_name=upload.fmt.name,
                filename=upload.display_name,
                file_size=upload.size,
                db_path=str(self.settings.db_path),
                analyzer_version=ANALYZER_VERSION,
                options=self._options(),
            )
        )
        return Submission(self.repo.get(job_id) or job, False)

    def _clone_cached(self, job_id: str, source: Job, filename: str, size: int) -> Job:
        """Re-use an identical file's analysis under a new id (cheap, keeps per-upload records)."""
        assert source.result_json is not None
        result = AnalysisResult.model_validate_json(source.result_json)
        metadata = result.metadata.model_copy(update={"filename": filename, "file_size": size})
        result = result.model_copy(update={"analysis_id": job_id, "metadata": metadata})
        self.repo.create(
            job_id,
            filename=filename,
            file_size=size,
            file_hash=source.file_hash,
            analyzer_version=source.analyzer_version,
        )
        self.repo.complete(
            job_id,
            result_json=result.model_dump_json(),
            duration=result.metadata.duration,
            key=result.music.key,
            bpm=result.music.bpm,
        )
        job = self.repo.get(job_id)
        assert job is not None
        return job

    def get_job(self, job_id: str) -> Job:
        if not _JOB_ID_RE.match(job_id):
            raise JobNotFoundError()
        job = self.repo.get(job_id)
        if job is None:
            raise JobNotFoundError()
        return job

    def get_result(self, job_id: str) -> AnalysisResult:
        job = self.get_job(job_id)
        if job.status is JobStatus.FAILED:
            raise JobFailedError(job.error_message, code=job.error_code)
        if job.status is not JobStatus.COMPLETED or not job.result_json:
            raise JobNotReadyError()
        return AnalysisResult.model_validate_json(job.result_json)
