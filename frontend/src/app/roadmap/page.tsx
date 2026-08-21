import type { Metadata } from 'next';
import { Compass, Sparkles } from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { ButtonLink } from '@/components/button-link';
import { RoadmapTimeline } from '@/components/roadmap-timeline';
import { RouteSwitcher } from '@/components/route-switcher';
import { SiteHeader } from '@/components/site-header';
import { apiOrNull } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import type { Roadmap, RoadmapSummary } from '@/lib/types';

export const metadata: Metadata = {
  title: 'Your route',
  description: 'Your week-by-week route, plotted from the knowledge graph.',
};

export default async function RoadmapPage() {
  await requireUser('/roadmap');
  const [roadmap, routes] = await Promise.all([
    apiOrNull<Roadmap>('/api/v1/roadmaps/current'),
    apiOrNull<RoadmapSummary[]>('/api/v1/roadmaps'),
  ]);

  return (
    <AppShell tutorContext={{ page: 'roadmap' }}>
      <SiteHeader />

      <main className="flex-1 px-4 py-10 sm:px-6 lg:px-8">
        {roadmap ? (
          <div className="mx-auto max-w-3xl">
            {routes && routes.length > 0 && <RouteSwitcher routes={routes} />}

            <header className="mb-12 border-b pb-8">
              <p className="eyebrow">{roadmap.track.target_role}</p>
              <h1 className="mt-3 font-display text-4xl font-semibold">
                {roadmap.track.title}
              </h1>

              <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
                <span className="tabular-nums">{roadmap.total_concepts} concepts</span>
                <span className="tabular-nums">{roadmap.weeks.length} weeks</span>
                <span className="capitalize tabular-nums">
                  {roadmap.pace} · {roadmap.daily_hours}h per day
                </span>
                {roadmap.target_date && (
                  <span className="tabular-nums">
                    on track for{' '}
                    {new Date(roadmap.target_date).toLocaleDateString(undefined, {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </span>
                )}
              </div>

              <div className="mt-7">
                <div className="mb-2 flex items-baseline justify-between text-sm">
                  <span className="eyebrow">Progress</span>
                  <span className="text-muted-foreground tabular-nums">
                    {roadmap.completed_concepts} / {roadmap.total_concepts} ·{' '}
                    {roadmap.percent_complete}%
                  </span>
                </div>
                <div
                  className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  aria-valuenow={roadmap.percent_complete}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Route completion"
                >
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${roadmap.percent_complete}%` }}
                  />
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-2">
                <ButtonLink variant="outline" size="sm" href="/explore">
                  Change route or pace
                </ButtonLink>
                <ButtonLink variant="ghost" size="sm" href="/dashboard">
                  See readiness
                </ButtonLink>
              </div>
            </header>

            <RoadmapTimeline roadmap={roadmap} />
          </div>
        ) : (
          <div className="mx-auto max-w-md py-24 text-center">
            <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-lg border bg-card">
              <Compass className="h-6 w-6 text-primary" />
            </div>
            <h1 className="font-display text-2xl font-semibold">No route plotted yet</h1>
            <p className="mt-3 text-muted-foreground">
              Pick a destination and tell us how much time you have. We will plot a
              week-by-week route through the graph and skip anything you already know.
            </p>
            <ButtonLink size="lg" className="mt-8" href="/explore">
              <Sparkles />
              Plot my route
            </ButtonLink>
          </div>
        )}
      </main>
    </AppShell>
  );
}
