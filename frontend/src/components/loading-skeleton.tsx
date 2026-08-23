import { Skeleton } from '@/components/ui/skeleton';

/**
 * Loading fallbacks for the two page shapes this app has.
 *
 * These matter more here than in most Next apps. The nonce-based CSP in
 * `src/proxy.ts` requires dynamic rendering, so nothing is statically served
 * and *every* navigation waits on a server render plus an API round trip.
 * Without a `loading.tsx` the browser simply holds the previous page, frozen,
 * for the whole of that — which reads as the app having hung.
 *
 * A skeleton is used rather than a spinner because these layouts are known
 * ahead of time: showing where the content will land makes the wait feel
 * shorter and stops the page jumping when it arrives.
 */

/** The signed-out marketing page: full-bleed hero, no sidebar. */
export function LandingSkeleton() {
  return (
    <div className="flex min-h-screen flex-col" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading SkillAtlas…</span>

      <header className="flex items-center justify-between px-8 py-6 sm:px-12">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-12 w-12 rounded-full" />
      </header>

      <main className="grid flex-1 items-center gap-12 px-8 pb-24 sm:px-12 lg:grid-cols-2">
        <div className="space-y-6">
          <Skeleton className="h-3 w-48" />
          <div className="space-y-4">
            <Skeleton className="h-14 w-full max-w-xl" />
            <Skeleton className="h-14 w-4/5 max-w-lg" />
            <Skeleton className="h-14 w-2/3 max-w-md" />
          </div>
          <div className="space-y-2 pt-2">
            <Skeleton className="h-4 w-full max-w-lg" />
            <Skeleton className="h-4 w-full max-w-md" />
            <Skeleton className="h-4 w-3/4 max-w-sm" />
          </div>
          <div className="flex gap-3 pt-4">
            <Skeleton className="h-11 w-40" />
            <Skeleton className="h-11 w-32" />
          </div>
          {/* The three headline counts under the hero. */}
          <div className="flex gap-12 pt-10">
            {[0, 1, 2].map((i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-9 w-20" />
                <Skeleton className="h-3 w-28" />
              </div>
            ))}
          </div>
        </div>

        {/* The map collage on the right, which only appears from lg up. */}
        <div className="hidden grid-cols-3 gap-3 lg:grid">
          {Array.from({ length: 9 }, (_, i) => (
            <Skeleton key={i} className="aspect-square w-full" />
          ))}
        </div>
      </main>
    </div>
  );
}

/** A signed-in page inside the app shell: fixed sidebar, content to the right. */
export function AppSkeleton() {
  return (
    <div className="flex min-h-screen w-full" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>

      {/* Sidebar. Hidden below lg, matching the real shell's drawer behaviour. */}
      <aside className="hidden w-64 shrink-0 flex-col gap-6 border-r p-6 lg:flex">
        <Skeleton className="h-5 w-32" />
        <div className="space-y-2 pt-4">
          {Array.from({ length: 9 }, (_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
        <div className="mt-auto space-y-2">
          <Skeleton className="h-10 w-full" />
        </div>
      </aside>

      <main className="flex-1 space-y-8 p-6 sm:p-10">
        <div className="space-y-3">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="h-9 w-full max-w-md" />
          <Skeleton className="h-4 w-full max-w-2xl" />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="space-y-3 rounded-lg border p-5">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
              <Skeleton className="h-8 w-24 pt-2" />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
