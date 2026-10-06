"""Job persistence (SQLite).

A fresh connection is opened per operation: SQLite connections are cheap, and this keeps
the repository safe to use from API threads and worker processes alike (WAL mode allows
one writer alongside concurrent readers). Replace with Firestore/Postgres by implementing
the same methods.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.models.job import Job, JobStatus, Stage

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    analyzer_version TEXT NOT NULL,
    duration REAL,
    key TEXT,
    bpm REAL,
    error_code TEXT,
    error_message TEXT,
    result_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs (file_hash, analyzer_version, status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs (created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        filename=row["filename"],
        file_size=row["file_size"],
        file_hash=row["file_hash"],
        status=JobStatus(row["status"]),
        stage=Stage(row["stage"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        analyzer_version=row["analyzer_version"],
        duration=row["duration"],
        key=row["key"],
        bpm=row["bpm"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        result_json=row["result_json"],
    )


class JobRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)

    def create(
        self,
        job_id: str,
        *,
        filename: str,
        file_size: int,
        file_hash: str,
        analyzer_version: str,
    ) -> Job:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, filename, file_size, file_hash, status, stage, created_at,"
                " updated_at, analyzer_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    filename,
                    file_size,
                    file_hash,
                    JobStatus.QUEUED.value,
                    Stage.QUEUED.value,
                    now,
                    now,
                    analyzer_version,
                ),
            )
        job = self.get(job_id)
        assert job is not None
        return job

    def get(self, job_id: str) -> Job | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def set_stage(self, job_id: str, stage: Stage) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET stage = ?, status = ?, updated_at = ?"
                " WHERE id = ? AND status IN (?, ?)",
                (
                    stage.value,
                    JobStatus.PROCESSING.value,
                    _now(),
                    job_id,
                    JobStatus.QUEUED.value,
                    JobStatus.PROCESSING.value,
                ),
            )

    def complete(
        self, job_id: str, *, result_json: str, duration: float, key: str, bpm: float
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, stage = ?, result_json = ?, duration = ?, key = ?,"
                " bpm = ?, updated_at = ?, error_code = NULL, error_message = NULL WHERE id = ?",
                (
                    JobStatus.COMPLETED.value,
                    Stage.COMPLETE.value,
                    result_json,
                    duration,
                    key,
                    bpm,
                    _now(),
                    job_id,
                ),
            )

    def fail(self, job_id: str, *, code: str, message: str) -> None:
        """Mark a job failed unless it already finished (first terminal state wins)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, stage = ?, error_code = ?, error_message = ?,"
                " updated_at = ? WHERE id = ? AND status NOT IN (?, ?)",
                (
                    JobStatus.FAILED.value,
                    Stage.FAILED.value,
                    code,
                    message,
                    _now(),
                    job_id,
                    JobStatus.COMPLETED.value,
                    JobStatus.FAILED.value,
                ),
            )

    def find_completed_by_hash(self, file_hash: str, analyzer_version: str) -> Job | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE file_hash = ? AND analyzer_version = ? AND status = ?"
                " ORDER BY created_at DESC LIMIT 1",
                (file_hash, analyzer_version, JobStatus.COMPLETED.value),
            ).fetchone()
        return _row_to_job(row) if row else None

    def count_active(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status IN (?, ?)",
                (JobStatus.QUEUED.value, JobStatus.PROCESSING.value),
            ).fetchone()
        return int(row[0])

    def fail_interrupted(self) -> int:
        """On startup: jobs left queued/processing by a previous process can never finish."""
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE jobs SET status = ?, stage = ?, error_code = ?, error_message = ?,"
                " updated_at = ? WHERE status IN (?, ?)",
                (
                    JobStatus.FAILED.value,
                    Stage.FAILED.value,
                    "interrupted",
                    "The server restarted during analysis. Please upload the file again.",
                    _now(),
                    JobStatus.QUEUED.value,
                    JobStatus.PROCESSING.value,
                ),
            )
            return cur.rowcount
