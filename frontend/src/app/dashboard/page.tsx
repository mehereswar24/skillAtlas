import type { Metadata } from 'next';
import Link from 'next/link';
import { BookOpen, Compass, Hammer, Sparkles, Trophy } from 'lucide-react';

import { AddToRoadmapButton } from '@/components/add-to-roadmap-button';
import { AppShell } from '@/components/app-shell';
import { ButtonLink } from '@/components/button-link';
import { SiteHeader } from '@/components/site-header';
import { VelocityChart } from '@/components/velocity-chart';
import { api, apiOrNull } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import { cn } from '@/lib/utils';
import type { Dashboard, PointsEvent } from '@/lib/types';

export const metadata: Metadata = {
  title: 'Dashboard',
  description: 'Your readiness for real roles, computed from what you have completed.',
};

export default async function DashboardPage() {
  await requireUser('/dashboard');
  const [data, ledger] = await Promise.all([
    api<Dashboard>('/api/v1/dashboard'),
    apiOrNull<PointsEvent[]>('/api/v1/progress/points?limit=8'),
  ]);
  const { stats, user } = data;
  const points = ledger ?? [];

  const rankedRoles = data.roles.filter((r) => r.percent > 0).slice(0, 6);
  const targetRoleTitle = data.missing_skills.length
    ? data.roles.find((r) => r.slug === data.missing_skills[0]!.role_slug)?.title
    : null;

  return (
    <AppShell>
      <SiteHeader />

      <main className="flex-1 px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl space-y-10">
          <header className="border-b pb-8">
            <p className="eyebrow">{greeting()}</p>
            <h1 className="mt-3 font-display text-4xl font-semibold">
              {user.display_name ?? 'Your position'}
            </h1>
            <p className="mt-3 text-muted-foreground">
              {data.current_track
                ? `Bearing set for ${data.current_track.title}.`
                : 'No bearing set. Choose a destination to start tracking readiness.'}
            </p>
          </header>

          {!data.current_track && (
            <div className="flex flex-col items-start gap-4 rounded-lg border border-dashed bg-card p-6 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="flex items-center gap-2 font-display text-lg font-semibold">
                  <Compass className="h-5 w-5 text-primary" />
                  Nothing plotted yet
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Everything on this page is computed from your own progress, so it
                  stays empty until you start.
                </p>
              </div>
              <ButtonLink href="/onboarding" className="shrink-0">
                <Sparkles />
                Choose a destination
              </ButtonLink>
            </div>
          )}

          {/* Stats as a single ruled band rather than four floating cards. */}
          <section className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border bg-border lg:grid-cols-4">
            <Stat
              label="Concepts covered"
              value={
                data.current_track
                  ? `${stats.concepts_completed}/${stats.concepts_total_in_track}`
                  : String(stats.concepts_completed)
              }
            />
            <Stat label="Hours logged" value={`${stats.hours_invested}h`} />
            <Stat
              label={`Level ${stats.level}`}
              value={`${stats.xp.toLocaleString()} XP`}
              footer={
                <>
                  <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-primary"
                      style={{
                        width: `${
                          stats.xp_for_next_level
                            ? (stats.xp_into_level / stats.xp_for_next_level) * 100
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                  <p className="mt-1.5 text-[11px] text-muted-foreground tabular-nums">
                    {stats.xp_into_level}/{stats.xp_for_next_level} to next
                  </p>
                </>
              }
            />
            <Stat
              label="Streak"
              value={`${stats.streak_days}d`}
              footer={
                <p className="mt-3 text-[11px] text-muted-foreground">
                  best {stats.longest_streak}d · active {stats.active_days_30}/30
                </p>
              }
            />
          </section>

          <div className="grid gap-10 lg:grid-cols-3">
            <div className="space-y-10 lg:col-span-2">
              <section>
                <SectionHeading
                  eyebrow="Readiness"
                  title="How close you are"
                  hint="Weighted by how much each concept matters for that role."
                />

                {rankedRoles.length > 0 ? (
                  <div className="mt-6 space-y-4">
                    {rankedRoles.map((role) => (
                      <div key={role.slug}>
                        <div className="mb-1.5 flex items-baseline justify-between gap-4 text-sm">
                          <span className="font-medium">{role.title}</span>
                          <span className="font-mono text-xs text-muted-foreground tabular-nums">
                            {role.percent}%
                          </span>
                        </div>
                        <div
                          className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
                          role="progressbar"
                          aria-valuenow={role.percent}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${role.title} readiness`}
                        >
                          <div
                            className={cn('h-full rounded-full', readinessColor(role.percent))}
                            style={{ width: `${role.percent}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-6 rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
                    Complete your first concept and readiness for every role starts
                    filling in.
                  </p>
                )}
              </section>

              <section>
                <SectionHeading
                  eyebrow="Velocity"
                  title="Ground covered"
                  hint="Minutes studied per day over the last 30 days."
                />
                <div className="mt-6">
                  <VelocityChart points={data.velocity} />
                </div>
              </section>

              {points.length > 0 && (
                <section>
                  <SectionHeading
                    eyebrow="Points"
                    title="Where the score came from"
                    hint="Every point is banked against something you finished."
                  />
                  <ul className="mt-5 divide-y rounded-lg border bg-card">
                    {points.slice(0, 8).map((event) => (
                      <li
                        key={event.id}
                        className="flex items-center justify-between gap-4 px-4 py-2.5 text-sm"
                      >
                        <span className="flex min-w-0 items-center gap-2.5">
                          {event.kind === 'project' ? (
                            <Hammer className="h-3.5 w-3.5 shrink-0 text-primary" />
                          ) : (
                            <BookOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          )}
                          <span className="truncate">{event.label}</span>
                        </span>
                        <span className="shrink-0 font-medium text-success tabular-nums">
                          +{event.points}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>

            <div className="space-y-10">
              {data.next_up.length > 0 && (
                <section>
                  <SectionHeading eyebrow="Next" title="Up ahead" />
                  <ul className="mt-5 space-y-1.5">
                    {data.next_up.map((concept) => (
                      <li key={concept.slug}>
                        <Link
                          href={`/concepts/${concept.slug}`}
                          className="group flex items-center justify-between gap-3 rounded-md border bg-card px-3 py-2.5 text-sm transition-colors hover:border-primary/60"
                        >
                          <span className="font-medium group-hover:text-primary">
                            {concept.name}
                          </span>
                          <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                            {concept.est_hours}h
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section>
                <SectionHeading
                  eyebrow="Gaps"
                  title="Biggest gains"
                  hint={
                    targetRoleTitle
                      ? `What would move ${targetRoleTitle} readiness the most.`
                      : undefined
                  }
                />

                {data.missing_skills.length > 0 ? (
                  <>
                    <ul className="mt-5 divide-y rounded-lg border bg-card">
                      {data.missing_skills.map((skill) => (
                        <li
                          key={skill.concept.slug}
                          className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm"
                        >
                          <Link
                            href={`/concepts/${skill.concept.slug}`}
                            className="font-medium hover:text-primary"
                          >
                            {skill.concept.name}
                          </Link>
                          <span className="shrink-0 font-mono text-xs text-primary tabular-nums">
                            +{skill.percent_contribution}%
                          </span>
                        </li>
                      ))}
                    </ul>

                    {data.missing_skills.some((s) => !s.in_roadmap) && (
                      <AddToRoadmapButton
                        conceptSlugs={data.missing_skills
                          .filter((s) => !s.in_roadmap)
                          .map((s) => s.concept.slug)}
                      />
                    )}
                  </>
                ) : (
                  <p className="mt-5 text-sm text-muted-foreground">
                    {stats.concepts_completed > 0
                      ? 'Nothing outstanding for your target role — aim at a more advanced one.'
                      : 'Choose a destination and your gaps will be listed here.'}
                  </p>
                )}
              </section>

              <section>
                <SectionHeading eyebrow="Awards" title="Badges" />
                {data.badges.length > 0 ? (
                  <ul className="mt-5 space-y-3">
                    {data.badges.map((badge) => (
                      <li key={badge.slug} className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border bg-card">
                          <Trophy className="h-3.5 w-3.5 text-primary" />
                        </span>
                        <span>
                          <span className="block text-sm font-medium">{badge.name}</span>
                          <span className="block text-xs text-muted-foreground">
                            {badge.description}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-5 text-sm text-muted-foreground">
                    None yet. The first arrives when you complete a concept.
                  </p>
                )}
              </section>
            </div>
          </div>
        </div>
      </main>
    </AppShell>
  );
}

function SectionHeading({
  eyebrow,
  title,
  hint,
}: {
  eyebrow: string;
  title: string;
  hint?: string;
}) {
  return (
    <div>
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-2 font-display text-2xl font-semibold">{title}</h2>
      {hint && <p className="mt-1.5 text-sm text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Stat({
  label,
  value,
  footer,
}: {
  label: string;
  value: string;
  footer?: React.ReactNode;
}) {
  return (
    <div className="bg-card p-5">
      <p className="eyebrow truncate">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold tabular-nums">{value}</p>
      {footer}
    </div>
  );
}

function readinessColor(percent: number): string {
  if (percent >= 80) return 'bg-success';
  if (percent >= 50) return 'bg-primary';
  if (percent >= 25) return 'bg-chart-3';
  return 'bg-chart-4';
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}
