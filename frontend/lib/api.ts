/**
 * Thin client for the Chord Analyzer REST API.
 * All music logic (transposition, simplification, capo) is computed by the API so the
 * browser, n8n and any other client get identical results.
 */
import type { AnalysisResult, HealthResponse, JobCreated, JobState } from "@/types/analysis";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

const NETWORK_MESSAGE =
  "Cannot reach the analysis server. Please check that the backend is running.";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string };
}

function toApiError(status: number, body: unknown): ApiError {
  const error = (body as ErrorBody | null)?.error;
  if (error?.message) return new ApiError(status, error.code ?? "http_error", error.message);
  return new ApiError(status, "http_error", `Request failed (${status}).`);
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      signal,
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "network_error", NETWORK_MESSAGE);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw toApiError(response.status, body);
  return body as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/health", signal);
}

export function getJob(jobId: string, signal?: AbortSignal): Promise<JobState> {
  return getJson<JobState>(`/api/jobs/${encodeURIComponent(jobId)}`, signal);
}

export interface ViewOptions {
  semitones?: number;
  targetKey?: string;
}

export function viewQuery({ semitones, targetKey }: ViewOptions): string {
  const params = new URLSearchParams();
  if (targetKey) params.set("target_key", targetKey);
  else if (semitones) params.set("semitones", String(semitones));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getResult(
  jobId: string,
  options: ViewOptions = {},
  signal?: AbortSignal,
): Promise<AnalysisResult> {
  return getJson<AnalysisResult>(
    `/api/jobs/${encodeURIComponent(jobId)}/result${viewQuery(options)}`,
    signal,
  );
}

/** Upload with real byte-level progress (fetch cannot report upload progress). */
export function uploadAudio(
  file: File,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<JobCreated> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/analyze`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as JobCreated);
      else reject(toApiError(xhr.status, xhr.response));
    };
    xhr.onerror = () => reject(new ApiError(0, "network_error", NETWORK_MESSAGE));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });

    const form = new FormData();
    form.append("file", file, file.name);
    xhr.send(form);
  });
}

export type ExportFormat = "txt" | "markdown" | "json";

export interface ExportOptions {
  semitones?: number;
  mode?: "original" | "beginner";
  download?: boolean;
}

export function exportUrl(
  jobId: string,
  format: ExportFormat,
  options: ExportOptions = {},
): string {
  const params = new URLSearchParams({ format });
  if (options.semitones) params.set("semitones", String(options.semitones));
  if (options.mode && options.mode !== "original") params.set("mode", options.mode);
  if (options.download === false) params.set("download", "false");
  return `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/export?${params.toString()}`;
}

export async function fetchExportText(
  jobId: string,
  format: ExportFormat,
  options: Omit<ExportOptions, "download"> = {},
): Promise<string> {
  let response: Response;
  try {
    response = await fetch(exportUrl(jobId, format, { ...options, download: false }));
  } catch {
    throw new ApiError(0, "network_error", NETWORK_MESSAGE);
  }
  if (!response.ok) throw toApiError(response.status, await response.json().catch(() => null));
  return response.text();
}
