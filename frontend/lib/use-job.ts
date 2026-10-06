"use client";

import { useEffect, useState } from "react";
import { ApiError, getJob } from "./api";
import type { JobState } from "@/types/analysis";

const POLL_MS = 1000;

/** Poll a job until it completes or fails. */
export function useJob(jobId: string): { job: JobState | null; error: ApiError | null } {
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    let failures = 0;

    async function poll() {
      try {
        const state = await getJob(jobId, controller.signal);
        failures = 0;
        setJob(state);
        setError(null);
        if (state.status === "completed" || state.status === "failed") return;
      } catch (err) {
        if (controller.signal.aborted) return;
        const apiError = err instanceof ApiError ? err : new ApiError(0, "unknown", String(err));
        // Not found is final; transient network errors are retried a few times.
        if (apiError.status === 404 || ++failures >= 5) {
          setError(apiError);
          return;
        }
      }
      timer = window.setTimeout(poll, POLL_MS);
    }

    void poll();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [jobId]);

  return { job, error };
}
