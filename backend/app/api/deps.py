"""FastAPI dependencies: service access, API key check and rate limiting."""

from __future__ import annotations

import hmac
from collections.abc import Callable

from fastapi import Request

from app.core.config import Settings
from app.core.errors import RateLimitedError, UnauthorizedError
from app.core.rate_limit import RateLimiter
from app.services.analysis_service import AnalysisService


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_service(request: Request) -> AnalysisService:
    service: AnalysisService = request.app.state.service
    return service


def client_id(request: Request) -> str:
    settings: Settings = request.app.state.settings
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_api_key(request: Request) -> None:
    """Optional shared-secret auth (``API_KEY``), e.g. for n8n or server-to-server calls."""
    expected = request.app.state.settings.api_key
    if not expected:
        return
    provided = request.headers.get("x-api-key", "")
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise UnauthorizedError()


def rate_limited(limiter_name: str) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        limiter: RateLimiter = request.app.state.rate_limiters[limiter_name]
        if not limiter.allow(client_id(request)):
            raise RateLimitedError()

    return dependency
