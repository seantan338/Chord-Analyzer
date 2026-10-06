"use client";

import { usePlayer } from "@/components/player/player-context";
import { cn } from "@/lib/cn";
import { formatTime } from "@/lib/format";
import { sectionClass } from "@/lib/sections";
import type { Section } from "@/types/analysis";

/** Proportional song-structure band. Click a section to jump to it. */
export function SectionStrip({ sections, duration }: { sections: Section[]; duration: number }) {
  const { seek } = usePlayer();
  if (sections.length === 0 || duration <= 0) return null;
  return (
    <div className="flex h-8 w-full overflow-hidden rounded-lg" aria-label="Song structure">
      {sections.map((section) => (
        <button
          key={section.id}
          type="button"
          onClick={() => seek(section.start)}
          title={`${section.name} · ${formatTime(section.start)}${section.name_is_inferred ? " (estimated)" : ""}`}
          className={cn(
            "truncate border-r border-white/60 px-2 text-left text-xs font-semibold last:border-r-0 dark:border-zinc-950/60",
            sectionClass(section.label),
          )}
          style={{ width: `${((section.end - section.start) / duration) * 100}%` }}
        >
          {section.name}
        </button>
      ))}
    </div>
  );
}
