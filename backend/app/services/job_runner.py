"""Job runners: where and how ``run_job`` executes.

* ``ProcessJobRunner`` (default): each job runs in its own OS process, supervised by a
  small thread pool. This gives a hard timeout (the process is killed), isolates crashes
  in native audio code, and returns all analysis memory to the OS after each job.
* ``InlineJobRunner``: runs synchronously in the caller (tests, debugging).

To scale out later, implement ``JobRunner`` on top of a queue (RQ, Celery, Cloud Tasks)
that calls ``app.services.worker.run_job``.
"""

from __future__ import annotations

import logging
import multiprocessing
import shutil
from concurrent.futures import ThreadPoolExecutor
from multiprocessing.context import ForkServerContext, SpawnContext
from typing import Protocol

from app.core.errors import AnalysisTimeoutError, ChordAnalyzerError
from app.services.job_repository import JobRepository
from app.services.worker import JobSpec, run_job

logger = logging.getLogger(__name__)

# Modules imported once in the fork server so each job starts without import overhead.
_PRELOAD = ["app.services.worker_preload"]


class JobRunner(Protocol):
    def submit(self, spec: JobSpec) -> None: ...

    def shutdown(self) -> None: ...


class InlineJobRunner:
    def submit(self, spec: JobSpec) -> None:
        run_job(spec)

    def shutdown(self) -> None:
        return None


class ProcessJobRunner:
    def __init__(self, repo: JobRepository, max_concurrent: int, timeout_seconds: int) -> None:
        self._repo = repo
        self._timeout = timeout_seconds
        self._pool = ThreadPoolExecutor(max_workers=max_concurrent, thread_name_prefix="job")
        self._ctx: ForkServerContext | SpawnContext
        if "forkserver" in multiprocessing.get_all_start_methods():
            forkserver = multiprocessing.get_context("forkserver")
            forkserver.set_forkserver_preload(_PRELOAD)
            self._ctx = forkserver
        else:  # Windows
            self._ctx = multiprocessing.get_context("spawn")

    def submit(self, spec: JobSpec) -> None:
        self._pool.submit(self._supervise, spec)

    def _supervise(self, spec: JobSpec) -> None:
        try:
            process = self._ctx.Process(target=run_job, args=(spec,), daemon=True)
            process.start()
            process.join(self._timeout)
            if process.is_alive():
                logger.warning("job %s timed out after %ss", spec.job_id, self._timeout)
                process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join()
                self._repo.fail(
                    spec.job_id,
                    code=AnalysisTimeoutError.code,
                    message=AnalysisTimeoutError.message,
                )
            elif process.exitcode != 0:
                logger.error("job %s worker exited with %s", spec.job_id, process.exitcode)
                self._repo.fail(
                    spec.job_id, code=ChordAnalyzerError.code, message=ChordAnalyzerError.message
                )
        except Exception:
            logger.exception("job %s supervision failed", spec.job_id)
            self._repo.fail(
                spec.job_id, code=ChordAnalyzerError.code, message=ChordAnalyzerError.message
            )
        finally:
            shutil.rmtree(spec.work_dir, ignore_errors=True)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
