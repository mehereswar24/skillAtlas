import type { Metadata } from 'next';
import Link from 'next/link';
import { BrainCircuit } from 'lucide-react';

import { OnboardingWizard } from '@/components/onboarding-wizard';
import { api } from '@/lib/api';
import { requireUser } from '@/lib/dal';
import type { Domain, TrackSummary } from '@/lib/types';

export const metadata: Metadata = {
  title: 'Plot your route',
  description: 'Choose a domain and a pace, and we will plot the route.',
};

const PACES = ['casual', 'steady', 'focused', 'intense'] as const;
type Pace = (typeof PACES)[number];

/** Map a stored hours-per-day figure back onto the nearest named pace. */
function paceFromHours(hours: number): Pace {
  if (hours <= 1) return 'casual';
  if (hours <= 2) return 'steady';
  if (hours <= 4) return 'focused';
  return 'intense';
}

export default async function OnboardingPage({
  searchParams,
}: {
  searchParams: Promise<{ track?: string; goal?: string }>;
}) {
  const [user, params] = await Promise.all([requireUser('/onboarding'), searchParams]);
  const [domains, tracks] = await Promise.all([
    api<Domain[]>('/api/v1/domains'),
    api<TrackSummary[]>('/api/v1/tracks'),
  ]);

  // Accept either a slug (?track=) or a goal title (?goal=) so links from
  // Explore and from the landing page both land here pre-filled.
  const preselected =
    tracks.find((t) => t.slug === params.track)?.slug ??
    tracks.find((t) => t.title.toLowerCase() === params.goal?.toLowerCase())?.slug;

  const initialPace = PACES.includes(user.profile.pace as Pace)
    ? (user.profile.pace as Pace)
    : paceFromHours(user.profile.daily_hours);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-muted/30 px-4 py-12">
      <Link href="/" className="mb-8 inline-flex items-center gap-2">
        <BrainCircuit className="h-8 w-8 text-primary" />
        <span className="text-xl font-bold tracking-tight">SkillAtlas</span>
      </Link>

      <OnboardingWizard
        domains={domains}
        tracks={tracks}
        preselectedSlug={preselected}
        initialPace={initialPace}
      />
    </div>
  );
}
