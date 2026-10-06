"use client";

import { FileAudio, Loader2, ShieldCheck, UploadCloud, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { useAudioFiles } from "@/components/audio-file-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError, getHealth, uploadAudio } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fileExtension, formatBytes, formatTime } from "@/lib/format";
import type { HealthResponse } from "@/types/analysis";

type Limits = HealthResponse["limits"];

const DEFAULT_LIMITS: Limits = {
  max_upload_mb: 50,
  allowed_extensions: [".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"],
  min_duration_seconds: 5,
  max_duration_seconds: 900,
};

export function validateFile(file: File, limits: Limits): string | null {
  if (!limits.allowed_extensions.includes(fileExtension(file.name))) {
    return "Unsupported file type. Please choose an MP3, WAV, M4A, AAC, FLAC or OGG file.";
  }
  if (file.size > limits.max_upload_mb * 1024 * 1024) {
    return `This file is ${formatBytes(file.size)}. The limit is ${limits.max_upload_mb} MB.`;
  }
  if (file.size === 0) return "This file is empty.";
  return null;
}

function readDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();
    const done = (value: number | null) => {
      URL.revokeObjectURL(url);
      resolve(value);
    };
    audio.preload = "metadata";
    audio.onloadedmetadata = () => done(Number.isFinite(audio.duration) ? audio.duration : null);
    audio.onerror = () => done(null);
    audio.src = url;
  });
}

export function UploadPanel() {
  const router = useRouter();
  const { setFile } = useAudioFiles();
  const inputRef = useRef<HTMLInputElement>(null);
  const [limits, setLimits] = useState<Limits>(DEFAULT_LIMITS);
  const [file, setSelected] = useState<File | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((health) => setLimits(health.limits))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  async function select(candidate: File | undefined) {
    if (!candidate) return;
    const problem = validateFile(candidate, limits);
    setError(problem);
    setSelected(problem ? null : candidate);
    setDuration(null);
    if (!problem) {
      const seconds = await readDuration(candidate);
      setDuration(seconds);
      if (seconds !== null && seconds < limits.min_duration_seconds) {
        setError(
          `This audio is only ${seconds.toFixed(1)}s long. Please upload at least ${limits.min_duration_seconds}s.`,
        );
        setSelected(null);
      }
    }
  }

  async function analyze() {
    if (!file) return;
    setError(null);
    setProgress(0);
    try {
      const created = await uploadAudio(file, setProgress);
      setFile(created.job_id, file);
      router.push(`/analysis/${created.job_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
      setProgress(null);
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    void select(event.dataTransfer.files[0]);
  }

  const uploading = progress !== null;
  const accept = [...limits.allowed_extensions, "audio/*"].join(",");

  return (
    <Card className="mx-auto w-full max-w-2xl">
      <CardContent className="space-y-5 pt-6">
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors",
            dragging
              ? "border-violet-500 bg-violet-50 dark:bg-violet-950/40"
              : "border-zinc-300 hover:border-violet-400 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800/50",
            uploading && "pointer-events-none opacity-60",
          )}
        >
          <UploadCloud className="h-10 w-10 text-violet-600" />
          <div>
            <div className="text-lg font-semibold">Upload Song</div>
            <div className="text-sm text-zinc-500">
              Drag & drop or click · MP3, WAV, M4A, AAC, FLAC, OGG · up to {limits.max_upload_mb} MB
            </div>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            className="sr-only"
            onChange={(e) => void select(e.target.files?.[0])}
            disabled={uploading}
          />
        </label>

        {file && (
          <div className="flex items-center gap-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <FileAudio className="h-8 w-8 shrink-0 text-violet-600" />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{file.name}</div>
              <div className="text-sm text-zinc-500">
                {formatBytes(file.size)} ·{" "}
                {duration !== null ? formatTime(duration) : "reading duration…"}
              </div>
            </div>
            {!uploading && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="Remove file"
                onClick={() => {
                  setSelected(null);
                  if (inputRef.current) inputRef.current.value = "";
                }}
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}

        {uploading && (
          <div className="space-y-1.5" aria-live="polite">
            <div className="flex justify-between text-sm">
              <span>{progress < 1 ? "Uploading…" : "Starting analysis…"}</span>
              <span className="tabular-nums text-zinc-500">{Math.round(progress * 100)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
              <div
                className="h-full bg-violet-600 transition-all"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
          </div>
        )}

        {error && (
          <p
            role="alert"
            className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950 dark:text-rose-300"
          >
            {error}
          </p>
        )}

        <Button
          size="lg"
          className="w-full"
          disabled={!file || uploading}
          onClick={() => void analyze()}
        >
          {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {uploading ? "Uploading" : "Analyze song"}
        </Button>

        <p className="flex items-center justify-center gap-1.5 text-xs text-zinc-500">
          <ShieldCheck className="h-3.5 w-3.5" /> Audio is processed temporarily and deleted after
          analysis.
        </p>
      </CardContent>
    </Card>
  );
}
