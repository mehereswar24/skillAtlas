import { AppSkeleton } from '@/components/loading-skeleton';

// This route renders inside AppShell, so its fallback needs the sidebar shape
// rather than the landing page's. Without it the root loading.tsx would flash
// a marketing hero on the way to a dashboard.
export default function Loading() {
  return <AppSkeleton />;
}
