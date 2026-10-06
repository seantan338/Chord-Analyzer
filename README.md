# Chord Analyzer

Upload a song and get, automatically:

- **Key** (with confidence and the most likely alternative), **tempo** (with half/double-time
  alternatives) and **time signature** (3/4 vs 4/4)
- **Beat- and bar-aligned chord progression** with timestamps and per-chord confidence
- **Detailed chords** (7ths, sus, dim, slash chords such as `G/B`) when the evidence is clear,
  plus **beginner chords** (`Cmaj7 → C`, `G/B → G`) for every chord
- **Song structure** (repeated sections A/B/C, with cautious Intro / Verse / Chorus / Bridge /
  Outro names marked as *estimated*)
- **Transposition** (±semitones or a target key) and **guitar capo suggestions**
- A **chord sheet** you can copy or export as **TXT, Markdown or JSON**
- An audio player: click any chord or bar to jump there; the current chord is highlighted

Chord detection is pure signal processing (constant-Q chroma + HMM). No LLM is involved, and
nothing depends on a paid API.

> **Accuracy.** Automatic chord recognition is not perfect. Expect roughly 55–70% of the song
> time to be labelled with the correct major/minor chord on real commercial recordings (more on
> clean, sparse arrangements), and fewer correct extended chords. Details in
> [docs/architecture.md](docs/architecture.md#accuracy-expectations).

---

## Contents

- [Quick start (Docker)](#quick-start-docker)
- [Requirements](#requirements)
- [Local development](#local-development)
- [Environment variables](#environment-variables)
- [API](#api)
- [Commands](#commands)
- [Production build & deployment](#production-build--deployment)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Docs](#docs)

---

## Quick start (Docker)

```bash
docker compose up --build
```

- Web app: <http://localhost:3000>
- API docs (Swagger): <http://localhost:8000/docs>

No test song at hand? `make demo-audio` renders a copyright-free synthetic song
(`demo-song.mp3`, G major, 92 BPM, with intro/verse/chorus/bridge/outro).

## Requirements

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.10+ (3.12 recommended) | backend |
| Node.js | 20.9+ (22 recommended) | frontend |
| FFmpeg | 4.x+ | `ffmpeg` and `ffprobe` must be on `PATH` |
| Docker | optional | for the containerised stack |

### FFmpeg setup

```bash
# macOS
brew install ffmpeg
# Ubuntu / Debian
sudo apt-get install -y ffmpeg
# Windows (PowerShell)
winget install Gyan.FFmpeg
```

Check with `ffmpeg -version` and `ffprobe -version`. `GET /api/health` reports `"ffmpeg": true`
when the API can find both.

## Local development

### Backend (FastAPI)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example .env            # optional, defaults work for local use
uvicorn app.main:app --reload --port 8000
```

The SQLite database and temporary uploads live in `backend/data/` (git-ignored).

### Frontend (Next.js)

```bash
cd frontend
npm ci
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local
npm run dev
```

Open <http://localhost:3000>, upload a song, and the analysis page opens automatically.

`make install`, `make dev-backend` and `make dev-frontend` do the same from the repo root.

## Environment variables

All variables are documented in [`.env.example`](.env.example). The important ones:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_DIR` | `./data` | SQLite DB + temp uploads |
| `MAX_UPLOAD_MB` | `50` | upload size limit |
| `MAX_DURATION_SECONDS` | `900` | longest accepted audio (15 min) |
| `JOB_RUNNER` | `process` | `process` (isolated + timeout) or `inline` (debug) |
| `JOB_TIMEOUT_SECONDS` | `300` | hard limit per analysis |
| `MAX_CONCURRENT_JOBS` | `2` | parallel analyses |
| `CHORD_VOCABULARY` | `extended` | `majmin` = only the 24 triads |
| `CORS_ORIGINS` | `http://localhost:3000` | comma-separated browser origins |
| `API_KEY` | _(empty)_ | if set, `/api/*` requires header `X-API-Key` |
| `RATE_LIMIT_ANALYZE_PER_MINUTE` | `10` | per client IP, `0` disables |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | frontend → API URL (build time) |

Secrets never belong in the repository: use `backend/.env`, `frontend/.env.local` or your
platform's secret settings.

## API

Interactive docs: `http://localhost:8000/docs`. Schema: [`docs/openapi.json`](docs/openapi.json).

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/analyze` | multipart `file` → `{job_id}`; `?wait=60` returns the full result when it finishes in time |
| `GET` | `/api/jobs/{job_id}` | status + current stage (`converting`, `tempo`, `chords`, …) |
| `GET` | `/api/jobs/{job_id}/result` | full analysis JSON; `?semitones=2` or `?target_key=D` transposes |
| `GET` | `/api/jobs/{job_id}/export` | `?format=txt\|markdown\|json&mode=original\|beginner&semitones=…` |
| `GET` | `/api/health` | health, FFmpeg availability and upload limits |

```bash
# asynchronous: submit, poll, fetch
curl -F "file=@song.mp3" http://localhost:8000/api/analyze
curl http://localhost:8000/api/jobs/<job_id>
curl "http://localhost:8000/api/jobs/<job_id>/result?target_key=D"

# one request (handy for n8n / scripts)
curl -F "file=@song.mp3" "http://localhost:8000/api/analyze?wait=120"

# chord sheet as Markdown, beginner chords, capo-friendly key
curl -OJ "http://localhost:8000/api/jobs/<job_id>/export?format=markdown&mode=beginner"
```

Errors always look like `{"error": {"code": "silent_audio", "message": "This audio appears to be silent."}}`
— the `code` is stable for automations, the `message` is safe to show to users.

Automation recipes (n8n → Google Sheets / Drive / Telegram): [docs/n8n.md](docs/n8n.md).

## Commands

| Where | Command | What |
| --- | --- | --- |
| root | `make check` | everything below |
| backend | `ruff check . && ruff format --check .` | lint + format |
| backend | `mypy app` | strict type check |
| backend | `pytest` | unit, DSP and API tests (≈30 s, uses FFmpeg) |
| backend | `pytest -m "not slow"` | fast subset |
| frontend | `npm run lint` / `npm run format:check` | ESLint / Prettier |
| frontend | `npm run typecheck` | `next typegen && tsc --noEmit` |
| frontend | `npm test` | Vitest unit tests |
| frontend | `npm run build` | production build |
| root | `make types` | regenerate `docs/openapi.json` and `frontend/types/api.generated.ts` |

The frontend's TypeScript types are generated from the backend's Pydantic models, so the API
contract has a single source of truth. Run `make types` after changing `backend/app/schemas`.

## Production build & deployment

**Docker images**

```bash
docker build -t chord-analyzer-api backend
docker build -t chord-analyzer-web --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com frontend
```

Both images run as non-root users. The API image includes FFmpeg and a health check; mount a
volume at `/data` to keep the job database. If Docker Hub rate-limits you, point the base images
at a mirror: `--build-arg BASE_IMAGE=mirror.gcr.io/library/python:3.12-slim` (API) /
`--build-arg NODE_IMAGE=mirror.gcr.io/library/node:22-alpine` (web).

**Zeabur (or any container PaaS)**

1. Create two services from this repository: root directory `backend` and `frontend`
   (each has a Dockerfile; both honour the platform's `PORT`).
2. Backend: set `CORS_ORIGINS=https://<your-frontend-domain>`, attach a volume at `/data`,
   optionally set `API_KEY` for server-to-server use.
3. Frontend: set the build variable `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-domain>`.

Scaling notes: one API instance with `MAX_CONCURRENT_JOBS=2` handles a few analyses at a time
(a 5-minute song needs roughly one CPU core for ~10 s and well under 1 GB RAM). For more throughput, see
[docs/architecture.md](docs/architecture.md#scaling-path).

## Project structure

```
backend/
  app/
    api/          FastAPI routes, dependencies (rate limit, API key), error handlers
    audio/        DSP pipeline: loader, chroma, tempo, meter, key, chords, refine, structure
    music/        pure music theory: notes, keys, chords, transpose, simplifier, capo
    exporters/    chord sheet model + TXT / Markdown / JSON (registry: add PDF here)
    services/     upload store, job repository (SQLite), job runner, result builder/views
    schemas/      Pydantic API contract (source of the TypeScript types)
    core/         settings, errors, logging, rate limiter
    devtools/     song synthesizer for tests and demos
  tests/          pytest (music theory, uploads, synthetic songs, API, exporters)
  scripts/        export_openapi, make_demo_audio
frontend/
  app/            Next.js App Router pages (upload, /analysis/[jobId])
  components/     upload, results (timeline, sheet, transpose, structure), player, ui
  lib/            API client, playback clock, chord/key/sheet helpers (+ Vitest tests)
  types/          generated API types + domain aliases
docs/             architecture, n8n guide, OpenAPI schema
docker-compose.yml
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Upload fails with “Cannot reach the analysis server” | Backend not running, or `NEXT_PUBLIC_API_BASE_URL` / `CORS_ORIGINS` don't match the URLs you use |
| `dependency_missing` / health shows `"ffmpeg": false` | Install FFmpeg or set `FFMPEG_PATH` / `FFPROBE_PATH` |
| `unsupported_format` for a real audio file | The content is checked, not the extension. Re-export the file as MP3/WAV |
| `insufficient_harmonic_content` | Drum-only, speech or noise. There are no chords to find |
| Analysis is slow on first run | numba compiles some functions once; later runs are faster. In Docker `NUMBA_CACHE_DIR` is set |
| Tempo is half or double what you expect | Both readings are often plausible; the alternative is shown next to the BPM |
| Key shows “Low confidence” | The relative major/minor or a neighbouring key fits almost as well; the alternative is shown |
| No playback after reloading the page | Audio is never stored on the server. Use “Attach audio to play” and pick the same file |
| `rate_limited` while testing | Raise `RATE_LIMIT_*` or set them to `0` in `backend/.env` |

## Docs

- [Architecture, pipeline and design decisions](docs/architecture.md)
- [n8n / automation guide](docs/n8n.md)
- [OpenAPI schema](docs/openapi.json)
