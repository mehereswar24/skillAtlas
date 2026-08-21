import type { Metadata } from 'next';
import Link from 'next/link';
import { CheckCircle2, Clock, Coins, Hammer } from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { ButtonLink } from '@/components/button-link';
import { SiteHeader } from '@/components/site-header';
import { RUNTIME_LABELS } from '@/components/workspace/runtime-protocol';
import { api } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import { cn } from '@/lib/utils';
import type { ProjectSummary } from '@/lib/types';

export const metadata: Metadata = {
  title: 'Build',
  description: 'Apply every concept you have covered in a project you actually run.',
};

export default async function ProjectsPage() {
  const user = await requireUser('/projects');
  const projects = await api<ProjectSummary[]>('/api/v1/projects');

  const shipped = projects.filter((project) => project.status === 'passed').length;
  const banked = projects
    .filter((project) => project.status === 'passed')
    .reduce((sum, project) => sum + project.xp_reward, 0);

  // Grouped by concept so the page reads as "the build half of your route"
  // rather than a flat exercise list.
  const byConcept = new Map<string, { name: string; slug: string; projects: ProjectSummary[] }>();
  for (const project of projects) {
    const group = byConcept.get(project.concept_slug) ?? {
      name: project.concept_name,
      slug: project.concept_slug,
      projects: [],
    };
    group.projects.push(project);
    byConcept.set(project.concept_slug, group);
  }

  return (
    <AppShell tutorContext={{ page: 'projects' }}>
      <SiteHeader />

      <main className="flex-1 px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <header className="mb-10 border-b pb-8">
            <p className="eyebrow">Apply it</p>
            <h1 className="mt-3 font-display text-4xl font-semibold">Build</h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Every concept ends in something you build, run and test — in the browser, with
              no setup. {projects.length} projects across your atlas.
            </p>

            {projects.length > 0 && (
              <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-2 text-sm">
                <div>
                  <dt className="text-muted-foreground">Shipped</dt>
                  <dd className="font-display text-2xl font-semibold tabular-nums">
                    {shipped}
                    <span className="text-base font-normal text-muted-foreground">
                      {' '}
                      / {projects.length}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Points banked</dt>
                  <dd className="font-display text-2xl font-semibold tabular-nums">{banked}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Level</dt>
                  <dd className="font-display text-2xl font-semibold tabular-nums">
                    {user.profile.level}
                  </dd>
                </div>
              </dl>
            )}
          </header>

          {projects.length === 0 ? (
            <div className="mx-auto max-w-md py-20 text-center">
              <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-lg border bg-card">
                <Hammer className="h-6 w-6 text-primary" />
              </div>
              <h2 className="font-display text-2xl font-semibold">No projects seeded yet</h2>
              <p className="mt-3 text-muted-foreground">
                Run <code className="rounded bg-muted px-1.5 py-0.5 text-sm">python -m app.seed.loader</code>{' '}
                in the backend to load them.
              </p>
              <ButtonLink className="mt-8" href="/roadmap">
                Back to your route
              </ButtonLink>
            </div>
          ) : (
            <div className="space-y-10">
              {[...byConcept.values()].map((group) => (
                <section key={group.slug}>
                  <h2 className="mb-4 flex items-baseline gap-3">
                    <Link
                      href={`/concepts/${group.slug}`}
                      className="font-display text-xl font-semibold hover:text-primary"
                    >
                      {group.name}
                    </Link>
                    <span className="text-xs text-muted-foreground">
                      {group.projects.length}{' '}
                      {group.projects.length === 1 ? 'project' : 'projects'}
                    </span>
                  </h2>

                  <ul className="grid gap-3 md:grid-cols-2">
                    {group.projects.map((project) => (
                      <li key={project.slug}>
                        <Link
                          href={`/projects/${project.slug}`}
                          className={cn(
                            'group flex h-full flex-col rounded-xl border bg-card p-5 transition-colors hover:border-primary/60',
                            project.status === 'passed' && 'border-success/40',
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <h3 className="font-semibold group-hover:text-primary">
                              {project.title}
                            </h3>
                            {project.status === 'passed' && (
                              <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                            )}
                          </div>
                          <p className="mt-1.5 flex-1 text-sm leading-relaxed text-muted-foreground">
                            {project.tagline}
                          </p>
                          <p className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
                            <span>{RUNTIME_LABELS[project.runtime] ?? project.runtime}</span>
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />~{project.est_minutes} min
                            </span>
                            <span className="flex items-center gap-1 tabular-nums">
                              <Coins className="h-3 w-3" />
                              {project.xp_reward}
                            </span>
                          </p>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </div>
      </main>
    </AppShell>
  );
}
