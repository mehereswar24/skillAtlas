import type { Domain, TrackSummary } from '@/lib/types';
import { api } from '@/lib/api';
import { LandingPageInteractive } from '@/components/landing-page-interactive';

export default async function Home() {
  const [domains, tracks] = await Promise.all([
    api<Domain[]>('/api/v1/domains'),
    api<TrackSummary[]>('/api/v1/tracks'),
  ]);
  const conceptCount = tracks.reduce((sum, t) => sum + t.concept_count, 0);
  const featured = tracks.slice(0, 6);

  return (
    <LandingPageInteractive
      domains={domains}
      tracks={tracks}
      conceptCount={conceptCount}
      featured={featured}
    />
  );
}
