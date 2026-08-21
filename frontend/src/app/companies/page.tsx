import type { Metadata } from 'next';
import Link from 'next/link';
import { Building2 } from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { ButtonLink } from '@/components/button-link';
import { SiteHeader } from '@/components/site-header';
import { api } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import type { CompanySummary } from '@/lib/types';

export const metadata: Metadata = {
  title: 'Companies',
  description: 'Who hires for what, what each role asks, and how ready you are.',
};

export default async function CompaniesPage() {
  await requireUser('/companies');
  const companies = await api<CompanySummary[]>('/api/v1/companies');

  const byIndustry = new Map<string, CompanySummary[]>();
  for (const company of companies) {
    byIndustry.set(company.industry, [...(byIndustry.get(company.industry) ?? []), company]);
  }

  return (
    <AppShell tutorContext={{ page: 'companies' }}>
      <SiteHeader />

      <main className="flex-1 px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <header className="mb-10 border-b pb-8">
            <p className="eyebrow">Where you are headed</p>
            <h1 className="mt-3 font-display text-4xl font-semibold">Companies</h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Pick a company to see the roles it hires for, what each one actually tests, and
              the questions people have been asked — every item linked to the source it came
              from.
            </p>
          </header>

          {companies.length === 0 ? (
            <div className="mx-auto max-w-md py-20 text-center">
              <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-lg border bg-card">
                <Building2 className="h-6 w-6 text-primary" />
              </div>
              <h2 className="font-display text-2xl font-semibold">No companies seeded yet</h2>
              <p className="mt-3 text-muted-foreground">
                Run{' '}
                <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                  python -m app.seed.loader
                </code>{' '}
                in the backend to load them.
              </p>
              <ButtonLink className="mt-8" href="/roadmap">
                Back to your route
              </ButtonLink>
            </div>
          ) : (
            <div className="space-y-10">
              {[...byIndustry.entries()].map(([industry, group]) => (
                <section key={industry}>
                  <h2 className="eyebrow mb-4">{industry}</h2>
                  <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {group.map((company) => (
                      <li key={company.slug}>
                        <Link
                          href={`/companies/${company.slug}`}
                          className="group flex h-full flex-col rounded-xl border bg-card p-5 transition-colors hover:border-primary/60"
                        >
                          <h3 className="font-display text-lg font-semibold group-hover:text-primary">
                            {company.name}
                          </h3>
                          {company.hq && (
                            <p className="mt-0.5 text-xs text-muted-foreground">{company.hq}</p>
                          )}
                          <p className="mt-2 line-clamp-3 flex-1 text-sm leading-relaxed text-muted-foreground">
                            {company.description}
                          </p>
                          <p className="mt-4 border-t pt-3 text-xs text-muted-foreground tabular-nums">
                            {company.role_count} {company.role_count === 1 ? 'role' : 'roles'}
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
