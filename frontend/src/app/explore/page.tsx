import type { Metadata } from 'next';

import { AppShell } from '@/components/app-shell';
import { DomainExplorer } from '@/components/domain-explorer';
import { SiteHeader } from '@/components/site-header';
import { api } from '@/lib/api';
import type { Domain, TrackSummary } from '@/lib/types';

export const metadata: Metadata = {
  title: 'Explore',
  description: 'Every domain and curated route in the atlas.',
};

export default async function ExplorePage() {
  const [domains, tracks, categories] = await Promise.all([
    api<Domain[]>('/api/v1/domains'),
    api<TrackSummary[]>('/api/v1/tracks'),
    api<string[]>('/api/v1/domains/categories'),
  ]);

  return (
    <AppShell tutorContext={{ page: 'explore' }}>
      <SiteHeader />

      <main className="flex-1 px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <header className="mb-10 border-b pb-8">
            <p className="eyebrow">The atlas</p>
            <h1 className="mt-3 font-display text-4xl font-semibold">Explore</h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              {domains.length} domains, {tracks.length} routes,{' '}
              {tracks.reduce((sum, t) => sum + t.concept_count, 0)} concepts. Every
              route is a prerequisite graph you can start from either end.
            </p>
          </header>

          <DomainExplorer domains={domains} tracks={tracks} categories={categories} />
        </div>
      </main>
    </AppShell>
  );
}
