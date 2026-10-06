# Using Chord Analyzer from n8n

The API is designed for automation:

- **One request is enough.** `POST /api/analyze?wait=180` uploads, waits up to 180 s and returns
  the full result in `result`.
- **Stable error codes.** Every error is `{"error": {"code", "message"}}`, so you can branch on
  `code` (`unsupported_format`, `silent_audio`, `analysis_timeout`, …).
- **Exports as text.** `GET /api/jobs/{id}/export?format=markdown` gives a ready chord sheet
  for Google Docs, Drive, Notion or e-mail.
- **Optional API key.** Set `API_KEY` on the backend and send it as the `X-API-Key` header
  (an n8n *Header Auth* credential).

## Example workflow: Drive folder → analysis → Sheets + Drive + Telegram

```
Google Drive Trigger (new file in "Songs/Inbox")
  → Google Drive: Download file                     (binary property: data)
  → HTTP Request: POST /api/analyze?wait=180         (multipart, file = data)
  → IF {{$json.status}} == "completed"
      true  → Set: pick fields → Google Sheets: Append row
                              → HTTP Request: GET export (markdown) → Google Drive: Upload
                              → Telegram: Send message
      false → Wait 15 s → HTTP Request: GET /api/jobs/{{$json.job_id}} → back to IF
```

### HTTP Request node: analyze

| Setting | Value |
| --- | --- |
| Method | `POST` |
| URL | `https://<your-api>/api/analyze?wait=180` |
| Authentication | Generic → Header Auth (`X-API-Key`), if `API_KEY` is set |
| Body content type | Form-Data (multipart) |
| Body parameter | type *n8n Binary File*, name `file`, input data field name `data` |
| Options → Timeout | `200000` ms |
| Options → Response | JSON; enable *Never Error* if you branch on `error.code` yourself |

Equivalent curl: `curl -H "X-API-Key: $KEY" -F "file=@song.mp3" "https://<api>/api/analyze?wait=180"`.

If the song finishes within `wait` seconds, the response is HTTP 200 with `status: "completed"`
and the full analysis in `result`. Otherwise it is HTTP 202 with `status: "queued"` or
`"processing"`; poll `GET /api/jobs/{{$json.job_id}}` until `status` is `completed`, then
`GET /api/jobs/{{$json.job_id}}/result`.

### Useful expressions (Set node → Google Sheets)

| Column | Expression |
| --- | --- |
| Title | `{{ $json.result.metadata.filename.replace(/\.[^.]+$/, '') }}` |
| Key | `{{ $json.result.music.key }}` |
| Key confidence | `{{ $json.result.music.key_confidence_level }}` |
| BPM | `{{ Math.round($json.result.music.bpm) }}` |
| Time | `{{ $json.result.music.time_signature }}` |
| Duration (s) | `{{ $json.result.metadata.duration }}` |
| Chords (beginner) | `{{ [...new Set($json.result.beginner_chords.map(c => c.chord).filter(c => c !== 'N'))].join(' ') }}` |
| Capo | `{{ $json.result.capo_suggestions[0] ? 'Capo ' + $json.result.capo_suggestions[0].capo + ' (' + $json.result.capo_suggestions[0].play_key + ')' : '' }}` |
| Sections | `{{ $json.result.sections.map(s => s.name).join(' → ') }}` |
| Analysis id | `{{ $json.job_id }}` |

### Chord sheet export node

`GET https://<api>/api/jobs/{{ $json.job_id }}/export?format=markdown&mode=beginner`, with
response format *File*. Pass the binary to *Google Drive → Upload*. Add `&target_key=D` (or
`&semitones=-2`) to export in another key.

### Telegram / e-mail summary

```
🎵 {{ $json.result.metadata.filename }}
Key {{ $json.result.music.key }} · {{ Math.round($json.result.music.bpm) }} BPM · {{ $json.result.music.time_signature }}
{{ $json.result.capo_note }}
```

## Error codes worth handling

| `error.code` | HTTP | Meaning / suggested action |
| --- | --- | --- |
| `unsupported_format` | 415 | not an audio file we can read; skip and notify |
| `file_too_large` | 413 | above `MAX_UPLOAD_MB` |
| `corrupted_audio`, `conversion_failed` | 422 | broken file; re-export |
| `audio_too_short`, `audio_too_long`, `silent_audio` | 422 | content problem |
| `insufficient_harmonic_content` | 422 | no chords to detect (speech, drums) |
| `analysis_timeout` | 422 (job) | retry later or use a shorter file |
| `queue_full`, `dependency_missing` | 503 | retry with backoff / server misconfigured |
| `rate_limited` | 429 | slow down (`RATE_LIMIT_ANALYZE_PER_MINUTE`) |
| `unauthorized` | 401 | missing/wrong `X-API-Key` |

Failed jobs report the same codes in `GET /api/jobs/{id}` under `error`.

## Roadmap for automation

- `callback_url` on `POST /api/analyze`, so the API calls an n8n Webhook when the job finishes
  (no polling).
- Batch endpoint for multiple files.
