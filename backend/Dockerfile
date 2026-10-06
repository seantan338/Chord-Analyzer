# Chord Analyzer API
# Override BASE_IMAGE to use a registry mirror, e.g. mirror.gcr.io/library/python:3.12-slim
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NUMBA_CACHE_DIR=/tmp/numba-cache \
    DATA_DIR=/data \
    APP_ENV=production

# FFmpeg decodes uploads; libsndfile reads the decoded WAV.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown appuser /data
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/health', timeout=4)"

# PORT is set by most PaaS (Zeabur, Render, Cloud Run); defaults to 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
