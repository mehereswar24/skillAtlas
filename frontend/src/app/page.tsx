import type { Domain, TrackSummary } from '@/lib/types';
import { api } from '@/lib/api';
import { LandingPageInteractive } from '@/components/landing-page-interactive';
import { TutorLauncher } from '@/components/tutor-launcher';
import { getCurrentUser } from '@/lib/dal';

export default async function Home() {
  const [domains, tracks, user] = await Promise.all([
    api<Domain[]>('/api/v1/domains'),
    api<TrackSummary[]>('/api/v1/tracks'),
    // Only to decide which door the helper knocks on. A signed-in visitor who
    // lands back here should get their own tutor, not the public helper.
    getCurrentUser(),
  ]);
  const conceptCount = tracks.reduce((sum, t) => sum + t.concept_count, 0);
  const featured = tracks.slice(0, 6);

  return (
    <>
      <LandingPageInteractive
        domains={domains}
        tracks={tracks}
        conceptCount={conceptCount}
        featured={featured}
        user={user}
      />
      {/* The landing page has no AppShell, so the helper is mounted directly.
          Signed out it answers through the rate-limited public endpoint. */}
      <TutorLauncher context={{ page: 'landing' }} signedIn={Boolean(user)} />
    </>
  );
}
