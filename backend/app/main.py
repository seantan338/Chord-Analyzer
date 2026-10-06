"""FastAPI application factory.

Run locally:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import error_response, register_error_handlers
from app.api.routes_health import router as health_router
from app.api.routes_jobs import router as jobs_router
from app.core.config import ANALYZER_VERSION, Settings, get_settings
from app.core.errors import FileTooLargeError
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimiter
from app.services.analysis_service import AnalysisService
from app.services.job_repository import JobRepository
from app.services.job_runner import InlineJobRunner, JobRunner, ProcessJobRunner
from app.services.uploads import UploadStore

logger = logging.getLogger(__name__)

SWEEP_INTERVAL_SECONDS = 600
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


def _build_runner(settings: Settings, repo: JobRepository) -> JobRunner:
    if settings.job_runner == "inline":
        return InlineJobRunner()
    return ProcessJobRunner(repo, settings.max_concurrent_jobs, settings.job_timeout_seconds)


async def _sweep_forever(uploads: UploadStore, ttl_seconds: float) -> None:
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
        uploads.sweep(ttl_seconds)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    repo = JobRepository(settings.db_path)
    uploads = UploadStore(settings.temp_root, settings.max_upload_bytes)
    ttl_seconds = settings.temp_file_ttl_minutes * 60.0

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repo.init_schema()
        uploads.prepare()
        interrupted = repo.fail_interrupted()
        if interrupted:
            logger.warning("marked %d interrupted jobs as failed", interrupted)
        uploads.sweep(0 if interrupted else ttl_seconds)
        runner = _build_runner(settings, repo)
        app.state.service = AnalysisService(settings, repo, runner, uploads)
        sweeper = asyncio.create_task(_sweep_forever(uploads, ttl_seconds))
        try:
            yield
        finally:
            sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sweeper
            runner.shutdown()

    app = FastAPI(
        title="Chord Analyzer API",
        version=ANALYZER_VERSION,
        description="Upload audio and get key, tempo, chords, song structure and chord sheets.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.rate_limiters = {
        "analyze": RateLimiter(settings.rate_limit_analyze_per_minute),
        "read": RateLimiter(settings.rate_limit_read_per_minute),
    }

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
        max_age=600,
    )

    @app.middleware("http")
    async def reject_oversized_uploads(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Fail fast on the declared size, before the multipart body is read.
        if request.method == "POST" and request.url.path == "/api/analyze":
            declared = request.headers.get("content-length", "")
            if (
                declared.isdigit()
                and int(declared) > settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES
            ):
                error = FileTooLargeError(
                    f"This file is too large. The limit is {settings.max_upload_mb} MB."
                )
                return error_response(error.status_code, error.code, error.message)
        return await call_next(request)

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(jobs_router)
    return app


app = create_app()
