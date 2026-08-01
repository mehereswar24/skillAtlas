import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  BookOpen,
  Clock,
  ExternalLink,
  FileText,
  FolderGit2,
  GraduationCap,
  Hammer,
  Lock,
  Newspaper,
  Video,
} from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { ConceptQuiz } from '@/components/concept-quiz';
import { Markdown } from '@/components/markdown';
import { SiteHeader } from '@/components/site-header';
import { TutorLauncher } from '@/components/tutor-launcher';
import { apiOrNull } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import { cn } from '@/lib/utils';
import type { ConceptDetail, ProjectSummary, Resource } from '@/lib/types';

const RESOURCE_META: Record<Resource['kind'], { icon: typeof Video; label: string }> = {
  video: { icon: Video, label: 'Watch' },
  doc: { icon: FileText, label: 'Documentation' },
  book: { icon: BookOpen, label: 'Books' },
  course: { icon: GraduationCap, label: 'Courses' },
  project: { icon: FolderGit2, label: 'Build something' },
  article: { icon: Newspaper, label: 'Articles' },
};

const KIND_ORDER: Resource['kind'][] = ['course', 'doc', 'video', 'article', 'book', 'project'];

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const concept = await apiOrNull<ConceptDetail>(`/api/v1/concepts/${slug}`);
  if (!concept) return { title: 'Concept not found' };
  return { title: concept.name, description: concept.summary };
}

export default async function ConceptPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  await requireUser(`/concepts/${slug}`);

  const [concept, projects] = await Promise.all([
    apiOrNull<ConceptDetail>(`/api/v1/concepts/${slug}`),
    apiOrNull<ProjectSummary[]>(`/api/v1/projects?concept=${slug}`),
  ]);
  if (!concept) notFound();

  const grouped = KIND_ORDER.map((kind) => ({
    kind,
    items: concept.resources.filter((r) => r.kind === kind),
  })).filter((group) => group.items.length > 0);

  return (
    <AppShell>
      <SiteHeader />

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6">
        <nav className="mb-6 text-sm text-muted-foreground">
          <Link href="/roadmap" className="hover:text-foreground">
            Roadmap
          </Link>
          <span className="mx-2">/</span>
          <span className="text-foreground">{concept.name}</span>
        </nav>

        <header className="mb-8">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-primary/10 px-2.5 py-1 font-medium text-primary">
              {concept.difficulty}
            </span>
            <span className="flex items-center gap-1 text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              ~{concept.est_hours} hours
            </span>
            {concept.status === 'completed' && (
              <span className="rounded-full bg-success/12 px-2.5 py-1 font-medium text-success">
                Completed
              </span>
            )}
          </div>

          <h1 className="font-display text-4xl font-semibold">{concept.name}</h1>
          <p className="mt-3 text-lg text-muted-foreground">{concept.summary}</p>
        </header>

        {concept.is_locked ? (
          <div className="rounded-xl border border-dashed bg-muted/30 p-8 text-center">
            <Lock className="mx-auto mb-4 h-8 w-8 text-muted-foreground" />
            <h2 className="font-display text-xl font-semibold">Not unlocked yet</h2>
            <p className="mx-auto mt-2 max-w-md text-muted-foreground">
              This one builds on things you have not finished. Complete these first:
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {concept.missing_prerequisites.map((prereq) => (
                <Link
                  key={prereq.slug}
                  href={`/concepts/${prereq.slug}`}
                  className="rounded-full border px-3 py-1.5 text-sm transition-colors hover:border-primary hover:text-primary"
                >
                  {prereq.name}
                </Link>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-10">
            <article>
              <Markdown>{concept.content_md}</Markdown>
            </article>

            {grouped.length > 0 && (
              <section>
                <h2 className="mb-5 font-display text-2xl font-semibold">Resources</h2>
                <div className="space-y-6">
                  {grouped.map(({ kind, items }) => {
                    const { icon: Icon, label } = RESOURCE_META[kind];
                    return (
                      <div key={kind}>
                        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                          <Icon className="h-4 w-4" />
                          {label}
                        </h3>
                        <ul className="space-y-2">
                          {items.map((resource) => (
                            <li key={resource.id}>
                              <a
                                href={resource.url}
                                target="_blank"
                                rel="noreferrer noopener"
                                className="group flex items-start gap-3 rounded-lg border p-3 transition-colors hover:border-primary/50 hover:bg-muted/40"
                              >
                                <span className="min-w-0 flex-1">
                                  <span className="block font-medium group-hover:text-primary">
                                    {resource.title}
                                  </span>
                                  <span className="mt-0.5 block text-xs text-muted-foreground">
                                    {[
                                      resource.provider,
                                      resource.duration_min
                                        ? `~${formatDuration(resource.duration_min)}`
                                        : null,
                                      resource.is_free ? 'Free' : 'Paid',
                                    ]
                                      .filter(Boolean)
                                      .join(' · ')}
                                  </span>
                                </span>
                                <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                              </a>
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {concept.interview_questions.length > 0 && (
              <section>
                <h2 className="mb-5 font-display text-2xl font-semibold">
                  Interview questions
                </h2>
                <div className="space-y-3">
                  {concept.interview_questions.map((question) => (
                    <details
                      key={question.id}
                      className="group rounded-xl border bg-card p-4 [&[open]]:bg-muted/30"
                    >
                      <summary className="flex cursor-pointer list-none items-start justify-between gap-4 font-medium">
                        {question.question}
                        <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                          {question.difficulty}
                        </span>
                      </summary>
                      {question.answer_md && (
                        <div className="mt-4 border-t pt-4">
                          <Markdown className="text-sm">{question.answer_md}</Markdown>
                        </div>
                      )}
                    </details>
                  ))}
                </div>
              </section>
            )}

            <ConceptQuiz
              slug={concept.slug}
              questions={concept.quiz}
              alreadyCompleted={concept.status === 'completed'}
              minutesSuggestion={concept.est_hours * 60}
            />

            {projects && projects.length > 0 && (
              <section>
                <h2 className="mb-2 font-display text-2xl font-semibold">Now build it</h2>
                <p className="mb-5 text-muted-foreground">
                  Reading it is half. These run in your browser — no setup, no local
                  toolchain.
                </p>
                <ul className="space-y-3">
                  {projects.map((project) => (
                    <li key={project.slug}>
                      <Link
                        href={`/projects/${project.slug}`}
                        className={cn(
                          'group flex items-start gap-4 rounded-xl border bg-card p-4 transition-colors hover:border-primary/60',
                          project.status === 'passed' && 'border-success/40',
                        )}
                      >
                        <Hammer
                          className={cn(
                            'mt-0.5 h-5 w-5 shrink-0',
                            project.status === 'passed' ? 'text-success' : 'text-primary',
                          )}
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block font-medium group-hover:text-primary">
                            {project.title}
                          </span>
                          <span className="mt-0.5 block text-sm text-muted-foreground">
                            {project.tagline}
                          </span>
                          <span className="mt-2 block text-xs text-muted-foreground tabular-nums">
                            ~{project.est_minutes} min · {project.xp_reward} points
                            {project.status === 'passed' && ' · shipped'}
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {concept.unlocks.length > 0 && (
              <section>
                <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
                  Completing this opens up
                </h2>
                <div className="flex flex-wrap gap-2">
                  {concept.unlocks.map((next) => (
                    <Link
                      key={next.slug}
                      href={`/concepts/${next.slug}`}
                      className="rounded-full border px-3 py-1.5 text-sm transition-colors hover:border-primary hover:text-primary"
                    >
                      {next.name}
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </main>

      <TutorLauncher conceptSlug={concept.slug} />
    </AppShell>
  );
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round(minutes / 60);
  return `${hours} ${hours === 1 ? 'hour' : 'hours'}`;
}
