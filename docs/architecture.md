# Chord Analyzer: architecture

## Starting point

The repository was empty: no existing stack, auth, database, deployment or UI to reuse. The
system was built from scratch with the recommended split: a **Next.js** web app and a
**FastAPI** analysis API. A single analysis engine serves the browser, n8n and any other client.

## Overview

```
 Browser (Next.js, client-rendered)                     n8n / scripts / other apps
 ├─ upload (XHR, real byte progress)                              │
 ├─ stage polling                                                 │
 ├─ local playback (File → object URL, never re-downloaded)       │
 └─ views: timeline · sheet · transpose · export                  │
          │  REST + JSON (CORS, optional X-API-Key)               │
          ▼                                                       ▼
 FastAPI ─────────────────────────────────────────────────────────────────────
  api/        routes, validation, rate limit, uniform errors
  services/   UploadStore → AnalysisService → JobRunner ──► worker process
              JobRepository (SQLite, WAL)                        │
              result_view (transpose on read), result_builder    │
  exporters/  chord sheet → txt / markdown / json                │
                                                                 ▼
  audio/  FFmpeg decode → CQT + harmonic mask → chroma (treble/bass)
          → onset/tempo/beats → beat grid → meter/downbeats
          → key profile → chord HMM (24 triads + N) → key refinement
          → chord refinement (7/sus/dim/slash) → bars → structure
  music/  pure theory: keys, chord symbols, transpose, simplify, capo
```

### Data flow of one analysis

1. `POST /api/analyze`: the upload is streamed to `DATA_DIR/tmp/<job_id>/<uuid>.upload`
   while it is SHA-256 hashed and size-checked. The content type is decided by magic bytes.
2. Cache: if a completed analysis with the same hash and analyzer version exists, it is
   cloned under a new job id and returned immediately (`cached: true`).
3. Otherwise a job row is created (`queued`) and handed to the `JobRunner`.
4. The worker process runs the pipeline and writes the current **stage** to SQLite after
   each step. The UI shows these stages; there are no invented percentages.
5. The result (`AnalysisResult`, ~30–80 KB JSON) is stored in the job row and the temp
   directory is deleted. **Audio is never kept.**
6. `GET /result` returns the stored result in the original key. Transposed views are
   computed on read (`?semitones=` / `?target_key=`), so every client gets identical,
   correctly spelled chords and capo suggestions.

## Audio pipeline

| Stage (`Stage`) | Module | What happens |
| --- | --- | --- |
| `converting` | `audio/loader.py`, `preprocess.py` | `ffprobe` validation, FFmpeg → mono 22.05 kHz float WAV with a **forced demuxer** and `-protocol_whitelist file`; silence / too short / too long checks; peak normalisation |
| `harmonic_features` | `audio/chroma.py` | Tuning estimation; constant-Q transforms (treble C3–C8 at 36 bins/oct; bass C1–B2 at 24 bins/oct); **harmonic/percussive separation in the CQT domain** (median filters along time vs. frequency → soft mask); log compression; chroma folding |
| `tempo` | `audio/tempo.py`, `grid.py`, `meter.py` | Onset envelope; tempo candidates {T, T/2, 2T, 2T/3, 3T/2} scored by tempogram strength × log-normal tempo prior; off-beat test to fix half-time readings (41 → 82 BPM); beat tracking; sub-frame BPM from a line fit; beat grid extended to the start/end; 3/4 vs 4/4 and downbeat phase from chord-change, bass-change and kick accents |
| `key` | `audio/key_detection.py` | Krumhansl–Kessler profile correlation on the energy-weighted chroma |
| `chords` | `chord_detection.py`, `chord_smoothing.py`, `chord_refine.py` | Beat-synchronous chroma with **bass-harmonic leakage compensation**; template + bass scores for 24 triads + no-chord; **HMM/Viterbi whose change probability depends on the position in the bar** (likely on downbeats, unlikely on weak beats) with a mild diatonic prior; single-beat low-confidence blips absorbed; key re-ranked with chord evidence (resolves relative major/minor); bar-by-bar refinement to 7/maj7/m7/sus2/sus4/dim and slash chords only with clear evidence |
| `structure` | `audio/structure.py` | Bar-level chroma + MFCC + loudness; 4-bar phrase embedding; recurrence + path graph; Laplacian spectral clustering (McFee & Ellis 2014), k by eigengap; short runs merged; boundaries refined with Foote novelty (±2 bars, preferring 4-bar phrases); labels A/B/C…; heuristic names |
| `finalizing` | `services/result_builder.py` | Spelling in the detected key, beginner chords, bars, capo advice, waveform peaks, confidence summary |

Performance (measured on a 4-vCPU container): a 2.5-minute MP3 takes about **7 s** from
upload to result; the DSP for a 4.7-minute song takes 7.6 s (≈5 s of it is the constant-Q
transforms). Each job runs in its own process forked from a pre-warmed fork server, so
librosa/scipy are already imported.

### Chord vocabulary and "stability first"

- The HMM only chooses among the **24 major/minor triads and N** (no chord). This keeps the
  sequence stable.
- `chord_refine` then looks at each bar of each segment and upgrades it only when the extra
  note is clearly present (7ths) or the replaced note is clearly absent (sus, dim). The
  inversion bass must clearly dominate the root (slash chords).
- Every segment carries `chord` (detailed) and `simplified` (triad). The UI's
  *Beginner* toggle and the exports use `simplified`.
- `CHORD_VOCABULARY=majmin` switches refinement off.

### Confidence

All confidences are **heuristic scores in 0–1**, not calibrated probabilities. The UI only
shows High (≥ 0.75), Medium (≥ 0.5) and Low.

| Item | Built from |
| --- | --- |
| Chord | template fit of the segment's average chroma, margin over the runner-up chord, segment length |
| Key | margin between the best and second key, profile correlation |
| Tempo | beat-interval regularity, pulse strength, half/double ambiguity |
| Time signature | contrast of downbeat cues for the chosen meter vs. the other |
| Structure | silhouette of the spectral clustering (per section and overall), eigengap |
| Section name | rule strength (e.g. a chorus that is ≥ 10% louder than other repeated sections). Names below 0.5 are not shown: the section stays "Section B" |

## API contract

`backend/app/schemas/analysis.py` defines `AnalysisResult` (schema version `1.0`):

```jsonc
{
  "analysis_id": "…",
  "metadata": { "filename", "duration", "file_size", "sample_rate", "tuning_offset_cents", "analyzed_at", "analyzer_version" },
  "music": { "key", "key_confidence", "key_confidence_level", "key_alternatives", "bpm", "bpm_alternatives", "time_signature", … },
  "rhythm": { "beats": [0.62, …], "downbeats": [0.62, …] },
  "sections": [{ "label": "B", "name": "Chorus", "name_is_inferred": true, "start", "end", "bar_start", "bar_end", "confidence" }],
  "bars": [{ "index": 1, "start", "end", "chords": [{ "chord": "G/B", "simplified": "G", "beats": 2, "start" }] }],
  "chords": [{ "start", "end", "chord": "G/B", "simplified": "G", "confidence", "confidence_level", "bar", "beat" }],
  "beginner_chords": [{ "start", "end", "chord": "G", "confidence" }],
  "capo_suggestions": [{ "capo": 3, "play_key": "C Major", "play_chords": ["C", "G", "Am", "F"], "playability": 0.9 }],
  "capo_note": "…",
  "waveform": [0.12, …],
  "confidence": { "key": {"value", "level"}, "tempo": …, "time_signature": …, "chords": …, "structure": … },
  "warnings": ["…"],
  "view": { "semitones": 0, "original_key": "G Major", "chord_mode": "original" }
}
```

The OpenAPI schema is exported to `docs/openapi.json`; the frontend's types are generated from
it (`npm run gen:api`). Timestamps are kept on every chord and bar, and the bar grid gives the
musically aligned view.

## Storage, privacy and lifecycle

| Data | Where | Lifetime |
| --- | --- | --- |
| Uploaded audio | `DATA_DIR/tmp/<job_id>/<uuid>.upload` | deleted right after analysis (and by a TTL sweeper as a safety net) |
| Decoded WAV | same temp dir | deleted right after loading |
| Job + result JSON | SQLite `DATA_DIR/chord_analyzer.db` | kept (no audio inside) |
| Playback | browser memory (object URL) | until the tab is closed |

`JobRepository` is the only persistence interface. Moving to Firestore/Postgres means
implementing its methods. If audio ever needs to be kept (for example a saved library),
add a storage adapter (Firebase Storage / GCS / S3) behind `UploadStore` and make retention
explicit and opt-in.

## Job execution

- `ProcessJobRunner`: a thread pool (`MAX_CONCURRENT_JOBS`) supervises one OS process per
  job, started from a **forkserver** that preloads the analysis libraries. The process is
  killed after `JOB_TIMEOUT_SECONDS` (`analysis_timeout`). A crash in native code only fails
  that job, and memory is returned to the OS after every job.
- `InlineJobRunner`: synchronous, for tests and debugging.
- On restart, jobs left `queued`/`processing` are marked failed (`interrupted`).
- Queue protection: `MAX_QUEUED_JOBS` → `503 queue_full`.

## Scaling path

1. **Vertical**: one analysis uses about one CPU core, so raise `MAX_CONCURRENT_JOBS` with
   the core count. Identical files are never analysed twice (hash cache).
2. **Horizontal**: move `JobRepository` to Postgres/Firestore and `JobRunner` to a queue
   (RQ/Celery/Cloud Tasks) consumed by separate worker containers built from the same image.
   Uploads then go to object storage (signed URL) instead of the local temp dir, and rate
   limiting moves to Redis or the API gateway.
3. **GPU (optional)**: only needed once deep chord models or stem separation are added; keep
   them in a dedicated worker pool so the CPU path stays cheap.

## Security

- Upload size enforced from `Content-Length` (fast reject) **and** while streaming.
- Extension allow-list, MIME sanity check, and **magic-byte sniffing**. Playlists (`#EXTM3U`),
  HTML and executables are rejected even when named `.mp3`.
- FFmpeg runs with an argument list (no shell), a forced demuxer, `-protocol_whitelist file`
  and timeouts.
- UUID file names; the client filename is sanitised and used only for display.
- Per-job temp directories (`0700`); non-root container users.
- Uniform error bodies; stack traces only in server logs.
- Optional shared-secret `X-API-Key` (constant-time compare) for server-to-server use.
- In-memory token-bucket rate limiting per client IP (`TRUST_PROXY_HEADERS` for
  `X-Forwarded-For` behind a proxy). For multiple replicas, move it to Redis or the gateway.
- Job ids are random 128-bit values validated by regex before any lookup.

## Extension points

| Need | Where |
| --- | --- |
| Better chord model (CNN/CRF, BTC transformer) | add a recogniser next to `chord_smoothing.smooth_chords` that returns `DetectedChord`s; keep `chord_refine` / result builder unchanged |
| PDF, MusicXML, MIDI export | new `render_*` function registered in `exporters/registry.py` |
| Cloud storage | adapter behind `UploadStore` / `JobRepository` |
| Task queue (RQ/Celery/Cloud Tasks) | implement `JobRunner.submit` to enqueue `worker.run_job(JobSpec)` |
| Webhook on completion | call a `callback_url` at the end of `worker.run_job` |

## Future integrations (designed, not built)

- **n8n / Google Sheets / Drive / Telegram**: already possible via REST (see
  [n8n.md](n8n.md)). Next step: `callback_url` webhooks instead of polling.
- **YouTube URL import**: a separate, rate-limited fetcher service that produces an audio file
  and calls the same upload path. Check rights/terms per platform before enabling.
- **Spotify metadata / lyrics import**: enrichment fields under `metadata`; lyrics–chord sync
  needs word timestamps (forced alignment) mapped onto `bars`.
- **Stem separation / vocal removal / karaoke**: an optional GPU worker (Demucs, MIT
  license) that writes stems to object storage; chord detection on the accompaniment stem
  also improves accuracy noticeably.
- **Piano / guitar chord diagrams**: frontend-only, from chord symbols.
- **PDF songbook, multi-song batch**: exporter + a batch endpoint queuing several jobs.
- **User accounts, saved library**: Firebase Auth + Firestore keyed by `analysis_id`.
  Owner-scoped access checks live in `AnalysisService`.
- **Manual chord editing / correction**: store user edits as an overlay (`edits[]`) on
  top of the immutable analysis, so re-analysis never overwrites them.
- **AI-assisted correction / explanations**: an LLM may suggest *formatting, section names,
  simplifications and theory explanations* using the chord sequence as input. It must never
  replace the audio-based detection.
- **Mobile PWA**: the client-rendered app needs only a manifest and a service worker.

## Accuracy expectations

Measured here on synthesized songs with known ground truth (see `backend/tests`): key, tempo
(±2%), meter, triads and the tested 7th/sus/dim/slash chords are recognised correctly,
including a recording detuned by 30 cents with added noise. Synthetic audio is much easier
than real productions. Realistic expectations for commercial recordings, based on published
MIREX results for comparable methods:

| Task | This MVP (chroma + HMM) | State of the art (deep models) |
| --- | --- | --- |
| Major/minor chords (time-weighted) | ~55–70% | ~80–85% |
| With 7ths / inversions | ~40–55% | ~65–75% |
| Global key (exact) | ~70–80% | ~80–85% |
| Tempo (allowing half/double) | ~85–90% | ~95% |
| Tempo (exact octave) | ~60–75% | ~75–85% |
| Section boundaries (±3 s) | ~50–60% F-measure | ~65% |
| Semantic section names | heuristic hints only | still unreliable |

Typical failure modes: dense distorted guitars, heavy vocals with sparse accompaniment, modal
or chromatic harmony, key changes (one global key is reported), rubato or tempo changes, and
songs that are almost one long section.

## Dependency choices

| Library | Why | License |
| --- | --- | --- |
| librosa, numpy, scipy, scikit-learn, soundfile | mature, pip-installable, fast enough on CPU | ISC / BSD |
| FFmpeg (subprocess) | decodes every common format | LGPL/GPL binary, invoked as an external program |
| FastAPI + Pydantic | typed contract → OpenAPI → TypeScript | MIT |
| Next.js, React, Tailwind | requested stack; client-rendered app | MIT |

Considered but **not** used by default:

- **madmom** has strong chord/beat models, but its pretrained models are CC BY-NC-SA, which
  rules out commercial use, and the package is hard to install on current Python.
- **Essentia** is AGPL-3.0, so a hosted service would have to publish its source.
- **Chordino / NNLS-chroma** (GPL, Vamp host required).
- **Deep chord models** (e.g. BTC) are a good Phase 5 upgrade behind the recogniser extension
  point, ideally combined with stem separation, after checking each model's license.

## Key decisions

- **Next.js** as requested. The app is fully client-rendered against the API, so moving to
  Vite (the team's usual stack) would be a mechanical change.
- **Music theory only on the server.** Transposition, spelling, simplification and capo
  logic live in `app/music` and are exposed through views. The frontend contains only
  presentation helpers, which avoids drift between the UI, exports and n8n.
- **CQT-domain HPSS** instead of STFT HPSS: ~1 s instead of ~24 s for a 5-minute song, with
  the same benefit for chroma.
- **Process-per-job** instead of threads: real timeouts and crash isolation without a broker.
- **SQLite** for the MVP, behind a repository interface.
