import type { Metadata } from 'next';
import Link from 'next/link';
import { Briefcase, ExternalLink, FileText, MapPin } from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { SiteHeader } from '@/components/site-header';
import { api } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import { cn } from '@/lib/utils';
import type { CompanySummary } from '@/lib/types';

import { NewApplicationForm } from './new-application-form';
import { StageControl } from './stage-control';
import { STAGE_TONE, type ApplicationBoard, type StageInfo } from './types';

export const metadata: Metadata = {
  title: 'Applications',
  description: 'Every job you are chasing, and what you still have to prepare for it.',
};

export default async function ApplicationsPage() {
  await requireUser('/applications');

  const [board, stages, companies] = await Promise.all([
    api<ApplicationBoard>('/api/v1/applications/board'),
    api<StageInfo[]>('/api/v1/applications/stages'),
    api<CompanySummary[]>('/api/v1/companies'),
  ]);

  const offers = board.columns.find((c) => c.stage === 'offer')?.applications.length ?? 0;

  return (
    <AppShell>
      <SiteHeader />

      <main className="flex-1 px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <header className="mb-8 border-b pb-8">
            <p className="eyebrow">Chase it</p>
            <h1 className="mt-3 font-display text-4xl font-semibold">Applications</h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Your board, kept by you. Link one of the companies we have researched and
              the card carries their documented interview loop and the concepts you are
              still missing for that role.
            </p>

            {board.total > 0 && (
              <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-2 text-sm">
                <Stat label="Tracked" value={board.total} />
                <Stat label="Live" value={board.active} />
                <Stat label="Offers" value={offers} />
              </dl>
            )}

            <div className="mt-6">
              <NewApplicationForm companies={companies} stages={stages} />
            </div>
          </header>

          {board.total === 0 ? (
            <div className="mx-auto max-w-md py-20 text-center">
              <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-lg border bg-card">
                <Briefcase className="h-6 w-6 text-primary" />
              </div>
              <h2 className="font-display text-2xl font-semibold">Nothing tracked yet</h2>
              <p className="mt-3 text-muted-foreground">
                Add the first job you are chasing. Saved, applied, screen, onsite — the
                board keeps the date of every move, so you can see where things actually
                stall.
              </p>
              <p className="mt-4 text-xs text-muted-foreground">
                SkillAtlas never reads job boards for you. Paste what you have.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 overflow-x-auto pb-4 lg:grid-cols-4">
              {board.columns
                .filter((column) => !column.is_terminal || column.applications.length > 0)
                .map((column) => (
                  <section key={column.stage} className="min-w-[15rem]">
                    <h2 className="mb-3 flex items-baseline justify-between gap-2 border-b pb-2">
                      <span
                        className={cn(
                          'text-sm font-semibold',
                          STAGE_TONE[column.stage],
                        )}
                      >
                        {column.label}
                      </span>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {column.applications.length}
                      </span>
                    </h2>

                    {column.applications.length === 0 ? (
                      <p className="rounded-lg border border-dashed p-4 text-xs text-muted-foreground">
                        Nothing here.
                      </p>
                    ) : (
                      <ul className="space-y-3">
                        {column.applications.map((application) => (
                          <li
                            key={application.id}
                            className="rounded-xl border bg-card p-4 transition-colors hover:border-primary/60"
                          >
                            <Link
                              href={`/applications/${application.id}`}
                              className="group block"
                            >
                              <p className="font-semibold group-hover:text-primary">
                                {application.role_title}
                              </p>
                              <p className="mt-0.5 text-sm text-muted-foreground">
                                {application.company_name}
                              </p>
                            </Link>

                            <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                              {application.location && (
                                <span className="inline-flex items-center gap-1">
                                  <MapPin className="h-3 w-3" />
                                  {application.location}
                                </span>
                              )}
                              {application.applied_on && (
                                <span className="tabular-nums">
                                  Applied {application.applied_on}
                                </span>
                              )}
                              {application.salary_note && (
                                <span>{application.salary_note}</span>
                              )}
                              {application.has_job_description && (
                                <span className="inline-flex items-center gap-1">
                                  <FileText className="h-3 w-3" />
                                  JD
                                </span>
                              )}
                              {application.source_url && (
                                <a
                                  href={application.source_url}
                                  target="_blank"
                                  rel="noreferrer noopener"
                                  className="inline-flex items-center gap-1 hover:text-foreground"
                                >
                                  <ExternalLink className="h-3 w-3" />
                                  Posting
                                </a>
                              )}
                            </p>

                            {application.company && (
                              <p className="mt-2 text-xs text-primary">
                                Prep from {application.company.name}
                                {application.company_role
                                  ? ` · ${application.company_role.title}`
                                  : ''}
                              </p>
                            )}

                            <div className="mt-3 border-t pt-3">
                              <StageControl
                                applicationId={application.id}
                                stage={application.stage}
                                stages={stages}
                              />
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                ))}
            </div>
          )}
        </div>
      </main>
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-display text-2xl font-semibold tabular-nums">{value}</dd>
    </div>
  );
}
