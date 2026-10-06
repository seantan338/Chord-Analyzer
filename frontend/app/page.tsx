import { UploadPanel } from "@/components/upload/UploadPanel";

export default function HomePage() {
  return (
    <div className="space-y-8 py-6">
      <div className="mx-auto max-w-2xl text-center">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          What chords are in this song?
        </h1>
        <p className="mt-3 text-zinc-600 dark:text-zinc-400">
          Upload a song to get its key, tempo, chord progression and a chord sheet you can play
          along with — in original or beginner-friendly chords.
        </p>
      </div>
      <UploadPanel />
    </div>
  );
}
