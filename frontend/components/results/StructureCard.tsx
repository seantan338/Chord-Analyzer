"use client";

import { usePlayer } from "@/components/player/player-context";
import { ConfidenceBadge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { formatTime } from "@/lib/format";
import { sectionClass } from "@/lib/sections";
import type { Section } from "@/types/analysis";

export function StructureCard({
  sections,
  className,
}: {
  sections: Section[];
  className?: string;
}) {
  const { seek } = usePlayer();
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Song structure</CardTitle>
        <p className="text-sm text-zinc-500">
          Sections with the same letter sound alike. Names such as “Chorus” are estimated from
          repetition and loudness — treat them as hints.
        </p>
      </CardHeader>
      <CardContent>
        {sections.length === 0 ? (
          <p className="text-sm text-zinc-500">
            No clear repeated sections were found (the song may be short or through-composed).
          </p>
        ) : (
          <ol className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {sections.map((section) => (
              <li key={section.id}>
                <button
                  type="button"
                  onClick={() => seek(section.start)}
                  className="flex w-full items-center gap-3 py-2 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                >
                  <span
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-sm font-bold",
                      sectionClass(section.label),
                    )}
                  >
                    {section.label}
                  </span>
                  <span className="flex-1">
                    <span className="font-medium">{section.name}</span>
                    {section.name_is_inferred && (
                      <span className="ml-1.5 text-xs text-zinc-400">estimated</span>
                    )}
                    <span className="block text-xs text-zinc-500">
                      {formatTime(section.start)}–{formatTime(section.end)} · bars{" "}
                      {section.bar_start}–{section.bar_end}
                    </span>
                  </span>
                  <ConfidenceBadge level={section.confidence_level} short />
                </button>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
