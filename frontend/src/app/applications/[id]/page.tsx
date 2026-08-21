import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { CheckCircle2, Circle, ExternalLink, MapPin } from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { Markdown } from '@/components/markdown';
import { SiteHeader } from '@/components/site-header';
import { api, apiOrNull } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import { cn } from '@/lib/utils';

import { ApplicationEditor } from './application-editor';
import { StageControl } from '../stage-control';
import { STAGE_TONE, type ApplicationDetail, type StageInfo } from '../types';

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const application = await apiOrNull<ApplicationDetail>(`/api/v1/applications/${id}`);
  if (!application) return { title: 'Application not found' };
  return {
    title: `${application.role_title} · ${application.company_name}`,
    description: 'Where this application stands, and what to prepare for it.',
  };
}

export default async function ApplicationPage({ params }: Params) {
  const { id } = await params;
  await requireUser(`/applications/${id}`);

  // Somebody else's application answers 404, not 403 — so this is the same
  // "not found" page either way, which is the point.
  const application = await apiOrNull<ApplicationDetail>(`/api/v1/applications/${id}`);
  if (!application) notFound();

  const stages = await api<StageInfo[]>('/api/v1/applications/stages');
  const stageLabel =
    stages.find((s) => s.value === application.stage)?.label ?? application.stage;
  const prep = application.prep;

  return (
    <AppShell>
      <SiteHeader />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10 sm:px-6">
        <nav className="mb-6 text-sm text-muted-foreground">
          <Link href="/applications" className="hover:text-foreground">
            Applications
          </Link>
          <span className="mx-2">/</span>
          <span className="text-foreground">{application.company_name}</span>
        </nav>

        <header className="mb-8 border-b pb-8">
          <p className={cn('eyebrow', STAGE_TONE[application.stage])}>{stageLabel}</p>
          <h1 className="mt-3 font-display text-4xl font-semibold">
            {application.role_title}
          </h1>
          <p className="mt-2 text-lg text-muted-foreground">
            {application.company ? (
              <Link
                href={`/companies/${application.company.slug}`}
                className="hover:text-foreground"
              >
                {application.company_name}
              </Link>
            ) : (
              application.company_name
            )}
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-muted-foreground">
            {application.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {application.location}
              </span>
            )}
            {application.applied_on && (
              <span className="tabular-nums">Applied {application.applied_on}</span>
            )}
            {application.salary_note && <span>{application.salary_note}</span>}
            {application.source_url && (
              <a
                href={application.source_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 hover:text-foreground"
              >
                The posting
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <StageControl
              applicationId={application.id}
              stage={application.stage}
              stages={stages}
              size="md"
            />
          </div>

          <div className="mt-4">
            <ApplicationEditor application={application} />
          </div>
        </header>

        {/* ---------------------------------------------------------------- */}
        {/* the timeline                                                      */}
        {/* ---------------------------------------------------------------- */}
        <section className="mb-10">
          <h2 className="mb-4 font-display text-xl font-semibold">Timeline</h2>
          <ol className="space-y-3 border-l pl-5">
            {application.events.map((event) => (
              <li key={event.id} className="relative">
                <span className="absolute -left-[1.42rem] top-1.5 h-2 w-2 rounded-full bg-primary" />
                <p className="text-sm font-medium">
                  {event.from_stage ? (
                    <>
                      {label(stages, event.from_stage)} →{' '}
                      <span className={STAGE_TONE[event.to_stage]}>
                        {label(stages, event.to_stage)}
                      </span>
                    </>
                  ) : (
                    <>Tracked as {label(stages, event.to_stage)}</>
                  )}
                </p>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {formatStamp(event.occurred_at)}
                </p>
                {event.note && <p className="mt-1 text-sm">{event.note}</p>}
              </li>
            ))}
          </ol>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* prep, only for a linked company                                   */}
        {/* ---------------------------------------------------------------- */}
        {prep ? (
          <section className="mb-10 rounded-xl border bg-card p-6">
            <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="font-display text-xl font-semibold">
                Preparing for {prep.company.name}
              </h2>
              {prep.fetched_on && (
                <p className="text-xs text-muted-foreground">
                  Researched, last checked {prep.fetched_on}
                </p>
              )}
            </div>

            {prep.company_role && (
              <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
                <Readiness
                  label="Their focus areas"
                  percent={prep.focus_readiness_percent}
                />
                {prep.role_readiness_percent !== null && (
                  <Readiness
                    label={`Readiness for ${prep.role_slug ?? 'this role'}`}
                    percent={prep.role_readiness_percent}
                  />
                )}
                <Link
                  href={`/companies/${prep.company.slug}/${prep.company_role.slug}`}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  {prep.question_count} sourced questions →
                </Link>
              </div>
            )}

            {prep.hiring_process_md && (
              <div className="mb-6">
                <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
                  Their documented loop
                </h3>
                <Markdown className="text-sm">{prep.hiring_process_md}</Markdown>
              </div>
            )}

            {prep.focus_areas.length > 0 && (
              <div className="mb-6">
                <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
                  What this role asks for
                </h3>
                <ul className="grid gap-2 sm:grid-cols-2">
                  {prep.focus_areas.map((area) => (
                    <li
                      key={area.label}
                      className="flex items-start gap-2 rounded-lg border p-3 text-sm"
                    >
                      {area.is_completed ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                      ) : (
                        <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      )}
                      <span className="min-w-0">
                        {area.concept_slug ? (
                          <Link
                            href={`/concepts/${area.concept_slug}`}
                            className="font-medium hover:text-primary"
                          >
                            {area.label}
                          </Link>
                        ) : (
                          <span className="font-medium">{area.label}</span>
                        )}
                        {area.notes && (
                          <span className="mt-0.5 block text-xs text-muted-foreground">
                            {area.notes}
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {prep.missing.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
                  Still missing for this role
                </h3>
                <ul className="space-y-1.5">
                  {prep.missing.map((gap) => (
                    <li key={gap.slug} className="flex items-baseline gap-3 text-sm">
                      <Link
                        href={`/concepts/${gap.slug}`}
                        className="font-medium hover:text-primary"
                      >
                        {gap.name}
                      </Link>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        +{gap.adds_percent}% readiness
                      </span>
                      {gap.is_in_roadmap && (
                        <span className="text-xs text-primary">on your route</span>
                      )}
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-xs text-muted-foreground">
                  Computed from concepts you have actually completed, weighted the same
                  way the dashboard weights them.
                </p>
              </div>
            )}
          </section>
        ) : (
          <section className="mb-10 rounded-xl border border-dashed p-6">
            <h2 className="font-display text-lg font-semibold">No prep material</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              This application is not linked to one of the 30 companies we have
              researched, so there is no documented interview loop to show. Edit it and
              link a company if it matches one.
            </p>
          </section>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* what the learner pasted                                           */}
        {/* ---------------------------------------------------------------- */}
        {application.job_description && (
          <section className="mb-10">
            <h2 className="mb-2 font-display text-xl font-semibold">Job description</h2>
            <p className="mb-3 text-xs text-muted-foreground">
              Pasted by you. SkillAtlas never fetches job listings.
            </p>
            <pre className="overflow-x-auto rounded-xl border bg-muted/40 p-4 text-sm whitespace-pre-wrap">
              {application.job_description}
            </pre>
          </section>
        )}

        {application.notes && (
          <section className="mb-10">
            <h2 className="mb-2 font-display text-xl font-semibold">Notes</h2>
            <p className="rounded-xl border bg-card p-4 text-sm whitespace-pre-wrap">
              {application.notes}
            </p>
          </section>
        )}
      </main>
    </AppShell>
  );
}

function label(stages: StageInfo[], value: string) {
  return stages.find((s) => s.value === value)?.label ?? value;
}

function formatStamp(value: string) {
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function Readiness({ label, percent }: { label: string; percent: number }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-display text-2xl font-semibold tabular-nums">{percent}%</p>
    </div>
  );
}
