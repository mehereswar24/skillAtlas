'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Loader2, Plus, X } from 'lucide-react';
import Link from 'next/link';

import { cn } from '@/lib/utils';
import type { RoadmapSummary } from '@/lib/types';

/**
 * The learner's routes, and which one is in focus.
 *
 * Several can run at once. Only the focused route drives the dashboard, the
 * tutor and the company "add to roadmap" actions, so switching focus is a real
 * action rather than a display preference — hence the round trip.
 */
export function RouteSwitcher({ routes }: { routes: RoadmapSummary[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState<number | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(id: number, method: 'POST' | 'DELETE') {
    setBusy(id);
    setError(null);
    try {
      const path = method === 'POST' ? `/api/roadmaps/${id}/focus` : `/api/roadmaps/${id}`;
      const response = await fetch(path, { method });
      if (!response.ok) {
        setError(
          method === 'POST' ? 'Could not switch route.' : 'Could not drop that route.',
        );
        return;
      }
      setConfirming(null);
      router.refresh();
    } catch {
      setError('Could not reach the server.');
    } finally {
      setBusy(null);
    }
  }

  if (routes.length === 0) return null;

  return (
    <section className="mb-8">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold text-muted-foreground">
          {routes.length === 1 ? 'Your route' : `Your ${routes.length} routes`}
        </h2>
        <Link
          href="/explore"
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          <Plus className="h-3.5 w-3.5" />
          Add another
        </Link>
      </div>

      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

      <ul className="grid gap-2 sm:grid-cols-2">
        {routes.map((route) => (
          <li
            key={route.id}
            className={cn(
              'rounded-lg border p-3 transition-colors',
              route.is_focused ? 'border-primary/60 bg-muted/40' : 'hover:border-primary/40',
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-medium">{route.track.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground tabular-nums">
                  {route.completed_concepts}/{route.total_concepts} done ·{' '}
                  {route.percent_complete}% · {route.pace}
                </p>
              </div>
              {route.is_focused ? (
                <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
                  <Check className="h-3 w-3" />
                  In focus
                </span>
              ) : (
                <button
                  type="button"
                  disabled={busy === route.id}
                  onClick={() => act(route.id, 'POST')}
                  className="shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors hover:border-primary hover:text-primary disabled:opacity-50"
                >
                  {busy === route.id ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    'Focus'
                  )}
                </button>
              )}
            </div>

            <div
              className="mt-2 h-1 overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-valuenow={route.percent_complete}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${route.track.title} progress`}
            >
              <div
                className="h-full rounded-full bg-primary transition-[width]"
                style={{ width: `${route.percent_complete}%` }}
              />
            </div>

            {confirming === route.id ? (
              <div className="mt-2 flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">Drop this route?</span>
                <button
                  type="button"
                  disabled={busy === route.id}
                  onClick={() => act(route.id, 'DELETE')}
                  className="font-medium text-destructive hover:underline disabled:opacity-50"
                >
                  Drop
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(null)}
                  className="text-muted-foreground hover:underline"
                >
                  Keep
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(route.id)}
                className="mt-2 inline-flex items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-destructive"
              >
                <X className="h-3 w-3" />
                Drop route
              </button>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">
        Dropping a route removes the plan, never the progress — concepts you have
        completed stay completed everywhere.
      </p>
    </section>
  );
}
