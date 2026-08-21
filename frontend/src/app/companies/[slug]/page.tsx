import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ArrowRight, ExternalLink, Star } from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { CompanyReviews } from '@/components/company-reviews';
import { Markdown } from '@/components/markdown';
import { SiteHeader } from '@/components/site-header';
import { apiOrNull } from '@/lib/api';
import { getCurrentUser } from '@/lib/dal';
import type { CompanyDetail, CompanyReviewList } from '@/lib/types';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const company = await apiOrNull<CompanyDetail>(`/api/v1/companies/${slug}`);
  if (!company) return { title: 'Company not found' };
  return { title: company.name, description: company.description ?? undefined };
}

export default async function CompanyPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  // Not `requireUser`: the reviews section below is readable signed out, and
  // the Proxy already keeps anonymous visitors off /companies. Anyone who does
  // reach this page without a session sees the profile and the reviews, and is
  // prompted to sign in before writing one.
  const user = await getCurrentUser();

  const [company, reviews] = await Promise.all([
    apiOrNull<CompanyDetail>(`/api/v1/companies/${slug}`),
    apiOrNull<CompanyReviewList>(`/api/v1/companies/${slug}/reviews`),
  ]);
  if (!company) notFound();

  return (
    <AppShell tutorContext={{ page: 'company', companySlug: company.slug }}>
      <SiteHeader />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10 sm:px-6">
        <nav className="mb-6 text-sm text-muted-foreground">
          <Link href="/companies" className="hover:text-foreground">
            Companies
          </Link>
          <span className="mx-2">/</span>
          <span className="text-foreground">{company.name}</span>
        </nav>

        <header className="mb-10 border-b pb-8">
          <p className="eyebrow">{company.industry}</p>
          <h1 className="mt-3 font-display text-4xl font-semibold">{company.name}</h1>
          {company.description && (
            <p className="mt-3 max-w-2xl text-lg text-muted-foreground">{company.description}</p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-muted-foreground">
            {company.hq && <span>{company.hq}</span>}
            {company.website && (
              <a
                href={company.website}
                target="_blank"
                rel="noreferrer noopener"
                className="flex items-center gap-1 hover:text-foreground"
              >
                Website
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
            {company.fetched_on && (
              <span className="text-xs">Last verified {formatDate(company.fetched_on)}</span>
            )}
            {company.reviews.average_rating !== null && (
              <a href="#reviews-heading" className="flex items-center gap-1.5 hover:text-foreground">
                <Star className="h-3.5 w-3.5 fill-amber-500 text-amber-500" />
                <span className="font-medium tabular-nums text-foreground">
                  {company.reviews.average_rating.toFixed(1)}
                </span>
                <span className="text-xs">
                  from {company.reviews.review_count}{' '}
                  {company.reviews.review_count === 1 ? 'member review' : 'member reviews'}
                </span>
              </a>
            )}
          </div>
        </header>

        {/* Says which half of this page is which. Everything above the reviews
            section is researched and cited; the reviews are not. */}
        <div className="mb-8 flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full border border-primary/40 bg-primary/10 px-2.5 py-0.5 font-medium text-primary">
            Researched profile
          </span>
          <span className="text-muted-foreground">
            Roles, process and links below are compiled from public sources and dated.
            Member reviews are further down, and are not verified.
          </span>
        </div>

        <div className="space-y-12">
          <section>
            <h2 className="mb-5 font-display text-2xl font-semibold">Roles</h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {company.roles.map((role) => (
                <li key={role.slug}>
                  <Link
                    href={`/companies/${company.slug}/${role.slug}`}
                    className="group flex h-full flex-col rounded-xl border bg-card p-5 transition-colors hover:border-primary/60"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="font-semibold group-hover:text-primary">{role.title}</h3>
                      <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                    </div>
                    <p className="mt-1.5 flex-1 text-sm leading-relaxed text-muted-foreground">
                      {role.description}
                    </p>

                    {role.readiness_percent !== null && (
                      <div className="mt-4">
                        <div className="mb-1.5 flex items-baseline justify-between text-xs">
                          <span className="text-muted-foreground">Your readiness</span>
                          <span className="font-medium tabular-nums">
                            {role.readiness_percent}%
                          </span>
                        </div>
                        <div
                          className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
                          role="progressbar"
                          aria-valuenow={role.readiness_percent}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`Readiness for ${role.title}`}
                        >
                          <div
                            className="h-full rounded-full bg-primary transition-all"
                            style={{ width: `${role.readiness_percent}%` }}
                          />
                        </div>
                      </div>
                    )}

                    <p className="mt-4 border-t pt-3 text-xs text-muted-foreground tabular-nums">
                      {role.focus_count} focus areas · {role.question_count} questions
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          {company.hiring_process_md && (
            <section>
              <h2 className="mb-5 font-display text-2xl font-semibold">How they hire</h2>
              <Markdown>{company.hiring_process_md}</Markdown>
            </section>
          )}

          {company.resources.length > 0 && (
            <section>
              <h2 className="mb-5 font-display text-2xl font-semibold">Straight from the source</h2>
              <ul className="space-y-2">
                {company.resources.map((resource) => (
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
                          {resource.kind}
                        </span>
                      </span>
                      <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <hr className="border-dashed" />

          <CompanyReviews
            companySlug={company.slug}
            companyName={company.name}
            roles={company.roles}
            signedIn={Boolean(user)}
            initial={
              reviews ?? {
                summary: company.reviews,
                reviews: [],
                viewer_can_write: Boolean(user),
                viewer_review_id: null,
              }
            }
          />
        </div>
      </main>
    </AppShell>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
