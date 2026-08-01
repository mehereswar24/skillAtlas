import Link from 'next/link';
import { Check, Circle, Lock, PlayCircle } from 'lucide-react';

import { cn } from '@/lib/utils';
import type { Roadmap, RoadmapItem } from '@/lib/types';

function ItemIcon({ item }: { item: RoadmapItem }) {
  if (item.status === 'completed')
    return <Check className="h-4 w-4 shrink-0 text-success" />;
  if (item.is_locked) return <Lock className="h-4 w-4 shrink-0 text-muted-foreground/60" />;
  if (item.status === 'in-progress')
    return <PlayCircle className="h-4 w-4 shrink-0 text-primary" />;
  return <Circle className="h-4 w-4 shrink-0 text-muted-foreground/50" />;
}

function ItemRow({ item }: { item: RoadmapItem }) {
  const body = (
    <>
      <ItemIcon item={item} />
      <span className="min-w-0 flex-1">
        <span
          className={cn(
            'block text-sm font-medium',
            item.status === 'completed' && 'text-muted-foreground line-through',
            item.is_locked && 'text-muted-foreground',
          )}
        >
          {item.concept.name}
        </span>
        {item.is_locked && item.missing_prerequisites.length > 0 && (
          <span className="mt-0.5 block text-xs text-muted-foreground">
            needs {item.missing_prerequisites.join(', ')}
          </span>
        )}
      </span>
      <span className="shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
        {item.concept.est_hours}h
      </span>
    </>
  );

  const base = 'flex items-center gap-3 rounded-md px-2.5 py-2 transition-colors';

  // A locked concept is not a link: opening it would only show a wall.
  return item.is_locked ? (
    <div className={cn(base, 'cursor-not-allowed opacity-65')} aria-disabled>
      {body}
    </div>
  ) : (
    <Link href={`/concepts/${item.concept.slug}`} className={cn(base, 'hover:bg-muted')}>
      {body}
    </Link>
  );
}

/**
 * The route, drawn as a survey line: each week is a station on a single
 * vertical rule, filled in as it is completed.
 */
export function RoadmapTimeline({ roadmap }: { roadmap: Roadmap }) {
  return (
    <ol className="relative space-y-8 border-l border-dashed border-border pl-8">
      {roadmap.weeks.map((week) => {
        const done = week.items.filter((i) => i.status === 'completed').length;
        const allDone = done === week.items.length;
        const started = done > 0;

        return (
          <li key={week.week_no} className="relative">
            <span
              className={cn(
                'absolute top-3 -left-[41px] flex h-[18px] w-[18px] items-center justify-center rounded-full border-2 border-background ring-1',
                allDone
                  ? 'bg-success ring-success'
                  : started
                    ? 'bg-primary ring-primary'
                    : 'bg-background ring-border',
              )}
              aria-hidden
            />

            <div className="rounded-lg border bg-card">
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-4 py-3">
                <h3 className="font-display text-base font-semibold">
                  Week {week.week_no}
                </h3>
                <span className="flex items-center gap-3 font-mono text-[11px] text-muted-foreground tabular-nums">
                  <span>{week.total_hours}h</span>
                  <span>
                    {done}/{week.items.length}
                  </span>
                </span>
              </div>

              <div className="p-1.5">
                {week.items.map((item) => (
                  <ItemRow key={item.id} item={item} />
                ))}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
