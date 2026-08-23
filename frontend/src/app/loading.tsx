import { LandingSkeleton } from '@/components/loading-skeleton';

// Root fallback. Also the one Next uses for any route below that has no
// loading.tsx of its own, so it stays deliberately close to the landing page.
export default function Loading() {
  return <LandingSkeleton />;
}
