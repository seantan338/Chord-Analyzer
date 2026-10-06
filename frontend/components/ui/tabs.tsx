"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface TabItem<T extends string> {
  id: T;
  label: string;
  icon?: ReactNode;
}

/** WAI-ARIA tabs with arrow-key navigation. Panels use id `${idPrefix}-panel-${id}`. */
export function TabList<T extends string>({
  idPrefix,
  items,
  active,
  onChange,
}: {
  idPrefix: string;
  items: TabItem<T>[];
  active: T;
  onChange: (id: T) => void;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = items.findIndex((item) => item.id === active);
    const delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!delta) return;
    event.preventDefault();
    const next = (index + delta + items.length) % items.length;
    onChange(items[next].id);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="tablist"
      onKeyDown={onKeyDown}
      className="flex gap-1 overflow-x-auto border-b border-zinc-200 dark:border-zinc-800"
    >
      {items.map((item, i) => {
        const selected = item.id === active;
        return (
          <button
            key={item.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            id={`${idPrefix}-tab-${item.id}`}
            role="tab"
            type="button"
            aria-selected={selected}
            aria-controls={`${idPrefix}-panel-${item.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.id)}
            className={cn(
              "-mb-px inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              selected
                ? "border-violet-600 text-violet-700 dark:text-violet-300"
                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200",
            )}
          >
            {item.icon}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({
  idPrefix,
  id,
  active,
  children,
}: {
  idPrefix: string;
  id: string;
  active: boolean;
  children: ReactNode;
}) {
  if (!active) return null;
  return (
    <div
      role="tabpanel"
      id={`${idPrefix}-panel-${id}`}
      aria-labelledby={`${idPrefix}-tab-${id}`}
      className="pt-5"
    >
      {children}
    </div>
  );
}
