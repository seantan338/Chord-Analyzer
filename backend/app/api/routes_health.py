"""Health and configuration endpoint (used by Docker health checks and the frontend)."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends

from app.api.deps import get_settings_dep
from app.audio.formats import ALLOWED_EXTENSIONS
from app.core.config import ANALYZER_VERSION, Settings
from app.schemas.jobs import HealthResponse, ServiceLimits

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service health and limits")
async def health(settings: Settings = Depends(get_settings_dep)) -> HealthResponse:
    ffmpeg_ok = bool(shutil.which(settings.ffmpeg_path) and shutil.which(settings.ffprobe_path))
    return HealthResponse(
        status="ok" if ffmpeg_ok else "degraded",
        version=ANALYZER_VERSION,
        ffmpeg=ffmpeg_ok,
        limits=ServiceLimits(
            max_upload_mb=settings.max_upload_mb,
            allowed_extensions=sorted(ALLOWED_EXTENSIONS),
            min_duration_seconds=settings.min_duration_seconds,
            max_duration_seconds=settings.max_duration_seconds,
        ),
    )
