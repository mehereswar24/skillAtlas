import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { CheckCircle2, Circle, ExternalLink, Route } from 'lucide-react';

import { AddFocusToRoadmap } from '@/components/add-focus-to-roadmap';
import { AppShell } from '@/components/app-shell';
import { Markdown } from '@/components/markdown';
import { SiteHeader } from '@/components/site-header';
import { apiOrNull } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import { cn } from '@/lib/utils';
import type { CompanyQuestion, CompanyRound, CompanyRoleDetail } from '@/lib/types';

/** Presented in the order a candidate meets them. */
const ROUND_ORDER: CompanyRound[] = [
  'aptitude',
  'coding',
  'technical',
  'system-design',
  'managerial',
  'hr',
];

const ROUND_LABELS: Record<CompanyRound, string> = {
  aptitude: 'Aptitude & reasoning',
  coding: 'Coding',
  technical: 'Technical',
  'system-design': 'System design',
  managerial: 'Managerial',
  hr: 'HR & fit',
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string; roleSlug: string }>;
}): Promise<Metadata> {
  const { slug, roleSlug } = await params;
  const role = await apiOrNull<CompanyRoleDetail>(
    `/api/v1/companies/${slug}/roles/${roleSlug}`,
  );
  if (!role) return { title: 'Role not found' };
  return {
    title: `${role.title} at ${role.company.name}`,
    description: role.description ?? undefined,
  };
}

export default async function CompanyRolePage({
  params,
}: {
  params: Promise<{ slug: string; roleSlug: string }>;
}) {
  const { slug, roleSlug } = await params;
  await requireUser(`/companies/${slug}/${roleSlug}`);

  const role = await apiOrNull<CompanyRoleDetail>(
    `/api/v1/companies/${slug}/roles/${roleSlug}`,
  );
  if (!role) notFound();

  const mapped = role.focus_areas.filter((area) => area.concept_slug);
  const remaining = mapped.filter((area) => !area.is_completed).length;

  const byRound = new Map<CompanyRound, CompanyQuestion[]>();
  for (const question of role.questions) {
    byRound.set(question.round, [...(byRound.get(question.round) ?? []), question]);
  }

  return (
    <AppShell tutorContext={{ page: 'role', companySlug: slug, roleSlug }}>
      <SiteHeader />

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6">
        <nav className="mb-6 text-sm text-muted-foreground">
          <Link href="/companies" className="hover:text-foreground">
            Companies
          </Link>
          <span className="mx-2">/</span>
          <Link href={`/companies/${role.company.slug}`} className="hover:text-foreground">
            {role.company.name}
          </Link>
          <span className="mx-2">/</span>
          <span className="text-foreground">{role.title}</span>
        </nav>

        <header className="mb-10 border-b pb-8">
          <p className="eyebrow">
            {role.company.name} · {role.level}
          </p>
          <h1 className="mt-3 font-display text-4xl font-semibold">{role.title}</h1>
          {role.description && (
            <p className="mt-3 text-lg text-muted-foreground">{role.description}</p>
          )}

          {mapped.length > 0 && (
            <div className="mt-7">
              <div className="mb-2 flex items-baseline justify-between text-sm">
                <span className="eyebrow">Your readiness</span>
                <span className="text-muted-foreground tabular-nums">
                  {mapped.length - remaining} / {mapped.length} focus areas ·{' '}
                  {role.readiness_percent}%
                </span>
              </div>
              <div
                className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-valuenow={role.readiness_percent}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Readiness for this role"
              >
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${role.readiness_percent}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Weighted by how heavily each area is tested, and counted only from concepts
                you have actually completed.
              </p>
            </div>
          )}

          {role.source_url && (
            <a
              href={role.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-5 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              Where this came from
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </header>

        <div className="space-y-12">
          {role.focus_md && (
            <section>
              <h2 className="mb-5 font-display text-2xl font-semibold">What to focus on</h2>
              <Markdown>{role.focus_md}</Markdown>
            </section>
          )}

          {role.focus_areas.length > 0 && (
            <section>
              <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
                <h2 className="font-display text-2xl font-semibold">Focus areas</h2>
                <AddFocusToRoadmap
                  companySlug={role.company.slug}
                  roleSlug={role.slug}
                  remaining={remaining}
                />
              </div>

              <ul className="space-y-2">
                {role.focus_areas.map((area) => {
                  const body = (
                    <>
                      {area.is_completed ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                      ) : (
                        <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      )}
                      <span className="min-w-0 flex-1">
                        <span className="block font-medium">{area.label}</span>
                        {area.notes && (
                          <span className="mt-0.5 block text-sm text-muted-foreground">
                            {area.notes}
                          </span>
                        )}
                        {area.in_roadmap && !area.is_completed && (
                          <span className="mt-1.5 inline-flex items-center gap-1 text-xs text-primary">
                            <Route className="h-3 w-3" />
                            On your route
                          </span>
                        )}
                      </span>
                      <span
                        className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                        title={`Weight ${area.weight} of 5 — how heavily this is tested`}
                      >
                        {area.weight}/5
                      </span>
                    </>
                  );

                  return (
                    <li key={area.id}>
                      {area.concept_slug ? (
                        <Link
                          href={`/concepts/${area.concept_slug}`}
                          className={cn(
                            'group flex items-start gap-3 rounded-xl border p-4 transition-colors hover:border-primary/50 hover:bg-muted/40',
                            area.is_completed && 'border-success/30',
                          )}
                        >
                          {body}
                        </Link>
                      ) : (
                        // No concept written for it yet: still worth naming,
                        // but there is nowhere honest to send them.
                        <div className="flex items-start gap-3 rounded-xl border border-dashed p-4">
                          {body}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {ROUND_ORDER.filter((round) => byRound.has(round)).map((round) => (
            <section key={round}>
              <h2 className="mb-1 font-display text-2xl font-semibold">
                {ROUND_LABELS[round]}
              </h2>
              <p className="mb-5 text-sm text-muted-foreground">
                {byRound.get(round)!.length} questions
              </p>

              <div className="space-y-3">
                {byRound.get(round)!.map((question) => (
                  <details
                    key={question.id}
                    className="group rounded-xl border bg-card p-4 [&[open]]:bg-muted/30"
                  >
                    <summary className="flex cursor-pointer list-none items-start justify-between gap-4 font-medium">
                      {question.question}
                      <span className="flex shrink-0 items-center gap-1.5">
                        {question.year && (
                          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground tabular-nums">
                            {question.year}
                          </span>
                        )}
                        <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                          {question.difficulty}
                        </span>
                      </span>
                    </summary>

                    <div className="mt-4 border-t pt-4">
                      {question.answer_md ? (
                        <Markdown className="text-sm">{question.answer_md}</Markdown>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No written answer yet — work it through, then check the source.
                        </p>
                      )}

                      <p className="mt-4 flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground">
                        {question.topic && <span>{question.topic}</span>}
                        <a
                          href={question.source_url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="inline-flex items-center gap-1 hover:text-foreground"
                        >
                          Source: {question.source_name}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </p>
                    </div>
                  </details>
                ))}
              </div>
            </section>
          ))}

          {role.questions.length === 0 && (
            <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
              No questions recorded for this role yet.
            </p>
          )}
        </div>
      </main>
    </AppShell>
  );
}
