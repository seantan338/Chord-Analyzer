# Chord Analyzer

Upload a song and get its key, tempo, time signature, beat-aligned chord progression,
song sections, beginner chords, capo suggestions, transposition and an exportable chord sheet.

> Work in progress — see `docs/architecture.md` once available. Full setup instructions are
> completed in Phase 4.

## Backend quick start

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Requires FFmpeg (`ffmpeg` and `ffprobe` on PATH).

```bash
curl -F "file=@song.mp3" http://localhost:8000/api/analyze        # -> {"job_id": "..."}
curl http://localhost:8000/api/jobs/<job_id>                       # -> status + stage
curl http://localhost:8000/api/jobs/<job_id>/result                # -> full analysis JSON
```

Checks: `ruff check . && ruff format --check . && mypy app && pytest`
