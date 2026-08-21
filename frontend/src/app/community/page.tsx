import type { Metadata } from 'next';

import { AppShell } from '@/components/app-shell';
import { CommunityFeed } from '@/components/community-feed';
import { SiteHeader } from '@/components/site-header';
import { api } from '@/lib/api';
import { getCurrentUser } from '@/lib/dal';
import type { CommunityPost, Domain } from '@/lib/types';

export const metadata: Metadata = {
  title: 'Community',
  description: 'Ask questions, share what worked, and compare notes with other learners.',
};

export default async function CommunityPage({
  searchParams,
}: {
  searchParams: Promise<{ sort?: string; domain?: string }>;
}) {
  const params = await searchParams;
  const sort = params.sort === 'top' ? 'top' : 'new';

  const query = new URLSearchParams({ sort, limit: '30' });
  if (params.domain) query.set('domain', params.domain);

  const [posts, domains, user] = await Promise.all([
    api<CommunityPost[]>(`/api/v1/community/posts?${query}`),
    api<Domain[]>('/api/v1/domains'),
    getCurrentUser(),
  ]);

  return (
    <AppShell tutorContext={{ page: 'community' }}>
      <SiteHeader />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10 sm:px-6">
        <header className="mb-8 border-b pb-8">
          <p className="eyebrow">Field notes</p>
          <h1 className="mt-3 font-display text-4xl font-semibold">Community</h1>
          <p className="mt-3 text-muted-foreground">
            Ask questions, share what worked, and compare notes with other learners.
          </p>
        </header>

        <CommunityFeed
          initialPosts={posts}
          domains={domains}
          signedIn={Boolean(user)}
          sort={sort}
          domainFilter={params.domain}
        />
      </main>
    </AppShell>
  );
}
