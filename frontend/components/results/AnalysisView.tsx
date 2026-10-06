"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { buttonClasses } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError, getResult } from "@/lib/api";
import { useJob } from "@/lib/use-job";
import type { AnalysisResult } from "@/types/analysis";
import { ProcessingStages } from "./ProcessingStages";
import { ResultsView } from "./ResultsView";

function Problem({ title, message }: { title: string; message: string }) {
  return (
    <Card className="mx-auto max-w-xl">
      <CardContent className="space-y-4 pt-6">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
          <div>
            <h1 className="text-lg font-semibold">{title}</h1>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{message}</p>
          </div>
        </div>
        <Link href="/" className={buttonClasses("secondary")}>
          Analyze another song
        </Link>
      </CardContent>
    </Card>
  );
}

export function AnalysisView({ jobId }: { jobId: string }) {
  const { job, error } = useJob(jobId);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [resultError, setResultError] = useState<ApiError | null>(null);
  const completed = job?.status === "completed";

  useEffect(() => {
    if (!completed) return;
    const controller = new AbortController();
    getResult(jobId, {}, controller.signal)
      .then(setResult)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setResultError(err instanceof ApiError ? err : new ApiError(0, "unknown", String(err)));
        }
      });
    return () => controller.abort();
  }, [jobId, completed]);

  if (error) {
    const notFound = error.status === 404;
    return (
      <Problem
        title={notFound ? "Analysis not found" : "Connection problem"}
        message={notFound ? "This analysis does not exist or has expired." : error.message}
      />
    );
  }
  if (resultError)
    return <Problem title="Could not load the result" message={resultError.message} />;
  if (!job) {
    return (
      <div className="flex justify-center py-20 text-zinc-500">
        <Loader2 className="h-6 w-6 animate-spin" aria-label="Loading" />
      </div>
    );
  }
  if (job.status === "failed") {
    return (
      <Problem
        title="We couldn't analyze this song"
        message={job.error?.message || "Something went wrong during analysis."}
      />
    );
  }
  if (!result) return <ProcessingStages job={job} />;
  return <ResultsView jobId={jobId} result={result} />;
}
