import type { VelocityPoint } from '@/lib/types';

/**
 * Minutes studied per day. A pure-CSS bar chart: no charting dependency, and
 * it renders on the server with the rest of the page.
 */
export function VelocityChart({ points }: { points: VelocityPoint[] }) {
  const peak = Math.max(...points.map((p) => p.minutes), 1);
  const totalMinutes = points.reduce((sum, p) => sum + p.minutes, 0);
  const activeDays = points.filter((p) => p.minutes > 0).length;

  if (totalMinutes === 0) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        Nothing logged yet. Complete a concept and your activity shows up here.
      </p>
    );
  }

  return (
    <div>
      <div className="flex h-40 items-end gap-[3px]" role="img" aria-label={ariaLabel(points)}>
        {points.map((point) => (
          <div
            key={point.day}
            className="group relative flex-1"
            style={{ height: '100%' }}
          >
            <div
              className={
                point.minutes > 0
                  ? 'absolute bottom-0 w-full rounded-t-sm bg-primary/80 transition-colors group-hover:bg-primary'
                  : 'absolute bottom-0 w-full rounded-t-sm bg-muted'
              }
              style={{
                height: point.minutes > 0 ? `${(point.minutes / peak) * 100}%` : '2px',
              }}
            />
            <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 rounded bg-foreground px-2 py-1 text-xs whitespace-nowrap text-background group-hover:block">
              {formatDay(point.day)} · {point.minutes} min
            </span>
          </div>
        ))}
      </div>

      <div className="mt-3 flex justify-between text-xs text-muted-foreground">
        <span>{formatDay(points[0]!.day)}</span>
        <span>
          {Math.round(totalMinutes / 60)}h across {activeDays}{' '}
          {activeDays === 1 ? 'day' : 'days'}
        </span>
        <span>{formatDay(points[points.length - 1]!.day)}</span>
      </div>
    </div>
  );
}

function formatDay(day: string): string {
  // `day` is an ISO date (YYYY-MM-DD); parse the parts directly so the label
  // does not shift by a day in timezones behind UTC.
  const [year, month, date] = day.split('-').map(Number);
  return new Date(year!, month! - 1, date!).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

function ariaLabel(points: VelocityPoint[]): string {
  const total = points.reduce((sum, p) => sum + p.minutes, 0);
  return `Daily study minutes over the last ${points.length} days, totalling ${total} minutes.`;
}
