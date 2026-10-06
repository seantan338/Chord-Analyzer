"""Job execution: runs the pipeline for one job and records the outcome.

``run_job`` is self-contained (it only receives a picklable ``JobSpec``) so it can run in
a separate process, a thread, or later a task queue worker (Celery, Cloud Tasks, ...).
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.audio.formats import SUPPORTED_FORMATS, AudioFormat
from app.audio.pipeline import PipelineOptions, analyze_file
from app.core.errors import ChordAnalyzerError
from app.services.job_repository import JobRepository
from app.services.result_builder import build_result

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    source_path: str
    work_dir: str
    format_name: str
    filename: str
    file_size: int
    db_path: str
    analyzer_version: str
    options: PipelineOptions


def _format(name: str) -> AudioFormat:
    return next(f for f in SUPPORTED_FORMATS if f.name == name)


def run_job(spec: JobSpec) -> None:
    repo = JobRepository(Path(spec.db_path))
    try:
        output = analyze_file(
            Path(spec.source_path),
            _format(spec.format_name),
            Path(spec.work_dir),
            spec.options,
            on_stage=lambda stage: repo.set_stage(spec.job_id, stage),
        )
        result = build_result(
            spec.job_id,
            output,
            filename=spec.filename,
            file_size=spec.file_size,
            analyzer_version=spec.analyzer_version,
        )
        repo.complete(
            spec.job_id,
            result_json=result.model_dump_json(),
            duration=result.metadata.duration,
            key=result.music.key,
            bpm=result.music.bpm,
        )
        logger.info("job %s completed", spec.job_id)
    except ChordAnalyzerError as exc:
        logger.info("job %s failed: %s", spec.job_id, exc.code)
        repo.fail(spec.job_id, code=exc.code, message=exc.message)
    except Exception:
        logger.exception("job %s crashed", spec.job_id)
        repo.fail(spec.job_id, code=ChordAnalyzerError.code, message=ChordAnalyzerError.message)
    finally:
        # Uploaded audio is never kept after analysis.
        shutil.rmtree(spec.work_dir, ignore_errors=True)
