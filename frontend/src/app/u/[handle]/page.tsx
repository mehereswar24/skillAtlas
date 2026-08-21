import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  Briefcase,
  CalendarDays,
  Code,
  Globe,
  MapPin,
  Sparkles,
  Trophy,
} from 'lucide-react';

import { LiveDemo } from '@/components/portfolio/live-demo';
import type { PublicPortfolio } from '@/components/portfolio/types';
import { RUNTIME_LABELS } from '@/components/workspace/runtime-protocol';
import { ThemeToggle } from '@/components/theme-toggle';
import { apiOrNull } from '@/lib/api';

/**
 * A learner's public page.
 *
 * Two things govern everything here.
 *
 * **It must render signed out.** No `requireUser`, no `AppShell` — the whole
 * point is a link you can put on a CV, and a redirect to /login would defeat
 * it. `src/proxy.ts` does not list `/u`, so the route stays open. The API call
 * still carries the session cookie when there is one, which is how the owner
 * gets a preview of their own unpublished page and nobody else does.
 *
 * **A 404 is a 404.** The backend returns the same not-found for "no such
 * handle" and "not published yet", and this page must not soften that into a
 * "this profile is private" message — that would confirm the handle exists.
 */

async function fetchProfile(handle: string) {
  return apiOrNull<PublicPortfolio>(
    `/api/v1/portfolio/${encodeURIComponent(handle)}`,
  );
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ handle: string }>;
}): Promise<Metadata> {
  const { handle } = await params;
  const profile = await fetchProfile(handle);
  if (!profile) return { title: 'Not found' };

  const description =
    profile.headline ||
    `${profile.display_name} on SkillAtlas — ${profile.projects.length} shipped projects.`;

  return {
    title: `${profile.display_name} (@${profile.handle})`,
    description,
    // An unpublished preview must never be indexed, whatever a crawler does
    // with the session cookie it does not have.
    robots: profile.is_preview ? { index: false, follow: false } : undefined,
    openGraph: { title: profile.display_name, description },
  };
}

const DATE = new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric' });

function formatMonth(iso: string) {
  return DATE.format(new Date(iso));
}

export default async function PublicProfilePage({
  params,
}: {
  params: Promise<{ handle: string }>;
}) {
  const { handle } = await params;
  const profile = await fetchProfile(handle);
  if (!profile) notFound();

  const links = [
    // lucide-react dropped its brand marks, so these are generic glyphs.
    { href: profile.links.github, label: 'GitHub', Icon: Code },
    { href: profile.links.linkedin, label: 'LinkedIn', Icon: Briefcase },
    { href: profile.links.website, label: 'Website', Icon: Globe },
  ].filter((link): link is { href: string; label: string; Icon: typeof Globe } =>
    Boolean(link.href),
  );

  const stats = [
    profile.projects_shipped !== null && {
      value: profile.projects_shipped,
      label: profile.projects_shipped === 1 ? 'project shipped' : 'projects shipped',
    },
    profile.concepts_completed !== null && {
      value: profile.concepts_completed,
      label: 'concepts completed',
    },
    profile.points !== null && { value: profile.points, label: 'points' },
    profile.level !== null && { value: profile.level, label: 'level' },
  ].filter(Boolean) as { value: number; label: string }[];

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/" className="font-display text-lg font-semibold">
            Skill<span className="text-primary">Atlas</span>
          </Link>
          <ThemeToggle />
        </div>
      </header>

      {profile.is_preview && (
        <p className="border-b border-warning/30 bg-warning/10 px-4 py-2.5 text-center text-sm">
          <strong className="font-semibold">Preview.</strong> This page is not
          published — nobody else can open it.{' '}
          <Link href="/portfolio" className="underline underline-offset-4">
            Publishing settings
          </Link>
        </p>
      )}

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10 sm:px-6">
        {/* --- identity ------------------------------------------------ */}
        <header>
          <h1 className="font-display text-4xl font-semibold">{profile.display_name}</h1>
          <p className="mt-1 font-mono text-sm text-muted-foreground">@{profile.handle}</p>
          {profile.headline && <p className="mt-3 text-lg">{profile.headline}</p>}

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {profile.location && (
              <span className="flex items-center gap-1.5">
                <MapPin className="h-3.5 w-3.5" />
                {profile.location}
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <CalendarDays className="h-3.5 w-3.5" />
              Learning here since {formatMonth(profile.joined_at)}
            </span>
          </div>

          {profile.bio && (
            <p className="mt-4 max-w-2xl whitespace-pre-line text-muted-foreground">
              {profile.bio}
            </p>
          )}

          {links.length > 0 && (
            <nav className="mt-4 flex flex-wrap gap-2">
              {links.map(({ href, label, Icon }) => (
                <a
                  key={label}
                  href={href}
                  target="_blank"
                  // noreferrer as well as noopener: this is a link a stranger
                  // supplied, on a page other strangers read.
                  rel="noopener noreferrer nofollow"
                  className="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </a>
              ))}
            </nav>
          )}
        </header>

        {stats.length > 0 && (
          <dl className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {stats.map((stat) => (
              <div key={stat.label} className="rounded-xl border bg-card px-4 py-3">
                <dt className="text-xs text-muted-foreground">{stat.label}</dt>
                <dd className="font-display text-2xl font-semibold tabular-nums">
                  {stat.value}
                </dd>
              </div>
            ))}
          </dl>
        )}

        {/* --- projects ------------------------------------------------ */}
        {profile.projects.length > 0 && (
          <section className="mt-12">
            <h2 className="font-display text-2xl font-semibold">Shipped</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Each of these passed its test suite here. Where the source is public you
              can run it yourself, in this page.
            </p>

            <div className="mt-5 space-y-5">
              {profile.projects.map((project) => (
                <article key={project.slug} className="rounded-xl border bg-card p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-display text-lg font-semibold">
                        {project.title}
                      </h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {project.note || project.tagline}
                      </p>
                    </div>
                    <span className="shrink-0 rounded-full bg-success/12 px-2.5 py-1 text-xs font-medium text-success">
                      {project.tests_passed}/{project.tests_total} tests
                    </span>
                  </div>

                  <div className="mt-3 mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span>{RUNTIME_LABELS[project.runtime] ?? project.runtime}</span>
                    <span aria-hidden>·</span>
                    <span>{project.difficulty}</span>
                    <span aria-hidden>·</span>
                    <span>{project.concept_name}</span>
                    <span aria-hidden>·</span>
                    <span>Shipped {formatMonth(project.shipped_at)}</span>
                    {project.attempts > 1 && (
                      <>
                        <span aria-hidden>·</span>
                        <span>
                          {project.attempts} attempts — which is how building works
                        </span>
                      </>
                    )}
                  </div>

                  <LiveDemo project={project} />
                </article>
              ))}
            </div>
          </section>
        )}

        {/* --- readiness ----------------------------------------------- */}
        {profile.readiness.length > 0 && (
          <section className="mt-12">
            <h2 className="font-display text-2xl font-semibold">Role readiness</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Share of each role&rsquo;s weighted skills completed here — not a claim
              about the rest of a career.
            </p>
            <ul className="mt-4 space-y-3">
              {profile.readiness.map((role) => (
                <li key={role.slug}>
                  <div className="mb-1 flex items-baseline justify-between text-sm">
                    <span className="font-medium">{role.title}</span>
                    <span className="tabular-nums text-muted-foreground">
                      {role.percent}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${role.percent}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* --- concepts ------------------------------------------------ */}
        {profile.tracks.length > 0 && (
          <section className="mt-12">
            <h2 className="font-display text-2xl font-semibold">Covered</h2>
            <div className="mt-4 space-y-6">
              {profile.tracks.map((track) => (
                <div key={track.slug}>
                  <h3 className="text-sm font-semibold">
                    {track.title}{' '}
                    <span className="font-normal text-muted-foreground tabular-nums">
                      {track.completed.length}/{track.track_total}
                    </span>
                  </h3>
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {track.completed.map((concept) => (
                      <li
                        key={`${track.slug}-${concept.slug}`}
                        className="rounded-full bg-muted px-2.5 py-1 text-xs"
                      >
                        {concept.name}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* --- badges -------------------------------------------------- */}
        {profile.badges.length > 0 && (
          <section className="mt-12">
            <h2 className="font-display text-2xl font-semibold">Badges</h2>
            <ul className="mt-4 flex flex-wrap gap-2">
              {profile.badges.map((badge) => (
                <li
                  key={badge.slug}
                  title={badge.description ?? undefined}
                  className="flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary"
                >
                  <Trophy className="h-3.5 w-3.5" />
                  {badge.name}
                </li>
              ))}
            </ul>
          </section>
        )}

        <footer className="mt-16 border-t pt-6 text-sm text-muted-foreground">
          <p className="flex flex-wrap items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5" />
            Everything above was earned on{' '}
            <Link href="/" className="font-medium text-foreground hover:underline">
              SkillAtlas
            </Link>
            . Projects run in your browser; nothing is executed on our servers.
          </p>
        </footer>
      </main>
    </div>
  );
}
