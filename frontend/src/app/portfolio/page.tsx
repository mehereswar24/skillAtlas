import type { Metadata } from 'next';
import Link from 'next/link';

import { AppShell } from '@/components/app-shell';
import { SiteHeader } from '@/components/site-header';
import { PortfolioSettingsForm } from '@/components/portfolio/portfolio-settings';
import type { PortfolioSettings } from '@/components/portfolio/types';
import { api } from '@/lib/api';
import { requireUser } from '@/lib/dal';

export const metadata: Metadata = {
  title: 'Your portfolio',
  description:
    'Choose a handle, decide what is public, and publish a page that runs the projects you built.',
};

/**
 * The owner's side of the portfolio — the opposite of `/u/[handle]` in every
 * way that matters. This one requires a session, is never indexed, and is the
 * only place any of it can be changed.
 */
export default async function PortfolioSettingsPage() {
  await requireUser('/portfolio');
  const settings = await api<PortfolioSettings>('/api/v1/portfolio/me');

  return (
    <AppShell>
      <SiteHeader />

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6">
        <header className="mb-8">
          <h1 className="font-display text-4xl font-semibold">Your portfolio</h1>
          <p className="mt-3 max-w-2xl text-lg text-muted-foreground">
            A page you can put on a CV, where the projects you built actually run —
            the visitor presses one button and watches your tests pass in their own
            browser.
          </p>
          <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
            It is private until you publish it, you choose what appears, and your
            email address is never part of it.{' '}
            <Link href="/projects" className="text-primary hover:underline">
              Shipped projects
            </Link>{' '}
            are the only ones that can be shown.
          </p>
        </header>

        <PortfolioSettingsForm initial={settings} />
      </main>
    </AppShell>
  );
}
