const PALETTE = [
  "bg-violet-200 text-violet-900 dark:bg-violet-900 dark:text-violet-100",
  "bg-sky-200 text-sky-900 dark:bg-sky-900 dark:text-sky-100",
  "bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100",
  "bg-emerald-200 text-emerald-900 dark:bg-emerald-900 dark:text-emerald-100",
  "bg-rose-200 text-rose-900 dark:bg-rose-900 dark:text-rose-100",
  "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-slate-100",
];

/** Same repetition label -> same colour (A, B, C ...). */
export function sectionClass(label: string): string {
  const index = Math.max(0, label.charCodeAt(0) - "A".charCodeAt(0));
  return PALETTE[index % PALETTE.length];
}
