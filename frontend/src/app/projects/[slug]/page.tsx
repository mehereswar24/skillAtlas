import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { Clock, Coins, Gauge } from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { Markdown } from '@/components/markdown';
import { SiteHeader } from '@/components/site-header';
import { CodeWorkspace } from '@/components/workspace/code-workspace';
import { RUNTIME_LABELS } from '@/components/workspace/runtime-protocol';
import { apiOrNull } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import type { ProjectDetail } from '@/lib/types';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const project = await apiOrNull<ProjectDetail>(`/api/v1/projects/${slug}`);
  if (!project) return { title: 'Project not found' };
  return { title: project.title, description: project.tagline };
}

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  await requireUser(`/projects/${slug}`);

  const project = await apiOrNull<ProjectDetail>(`/api/v1/projects/${slug}`);
  if (!project) notFound();

  return (
    <AppShell tutorContext={{ page: 'project', projectSlug: project.slug }}>
      <SiteHeader />

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6">
        <nav className="mb-6 text-sm text-muted-foreground">
          <Link href="/projects" className="hover:text-foreground">
            Build
          </Link>
          <span className="mx-2">/</span>
          <Link href={`/concepts/${project.concept_slug}`} className="hover:text-foreground">
            {project.concept_name}
          </Link>
          <span className="mx-2">/</span>
          <span className="text-foreground">{project.title}</span>
        </nav>

        <header className="mb-8">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-primary/10 px-2.5 py-1 font-medium text-primary">
              {project.difficulty}
            </span>
            <span className="flex items-center gap-1 text-muted-foreground">
              <Gauge className="h-3.5 w-3.5" />
              {RUNTIME_LABELS[project.runtime] ?? project.runtime}
            </span>
            <span className="flex items-center gap-1 text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />~{project.est_minutes} min
            </span>
            <span className="flex items-center gap-1 text-muted-foreground">
              <Coins className="h-3.5 w-3.5" />
              {project.xp_reward} points
            </span>
            {project.status === 'passed' && (
              <span className="rounded-full bg-success/12 px-2.5 py-1 font-medium text-success">
                Shipped
              </span>
            )}
          </div>

          <h1 className="font-display text-4xl font-semibold">{project.title}</h1>
          <p className="mt-3 text-lg text-muted-foreground">{project.tagline}</p>
        </header>

        <div className="grid gap-8 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)] lg:items-start">
          <article className="lg:sticky lg:top-6">
            <Markdown className="text-sm">{project.brief_md}</Markdown>

            {project.attempts > 0 && (
              <p className="mt-6 border-t pt-4 text-xs text-muted-foreground">
                {project.attempts} previous {project.attempts === 1 ? 'attempt' : 'attempts'}
                {project.best_passed > 0 && ` · best ${project.best_passed}/${project.tests.length}`}
              </p>
            )}
          </article>

          <CodeWorkspace project={project} />
        </div>
      </main>
    </AppShell>
  );
}
