'use client';

import { useEffect } from 'react';
import Link from 'next/link';

/**
 * The app-wide error boundary.
 *
 * Without one, anything a Server Component throws — most often
 * `TypeError: fetch failed` when the FastAPI backend is restarting or has
 * dropped the connection — reaches the browser as Next's bare error screen,
 * which in production says only "Application error: a server-side exception
 * has occurred". This says what is actually wrong and offers a way forward.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Server Component errors arrive here already stripped of their message in
    // production, so log whatever we do have for whoever is watching the tab.
    console.error('SkillAtlas page error:', error);
  }, [error]);

  // `fetch failed` is what Node throws for ECONNREFUSED/ECONNRESET, so it is a
  // reliable signal that the API — not this page — is the thing that broke.
  const apiUnreachable =
    error.message.includes('fetch failed') || error.message.includes('ECONNREFUSED');

  return (
    <main className="flex min-h-[60vh] flex-col items-center justify-center gap-5 px-6 py-24 text-center">
      <p className="eyebrow">{apiUnreachable ? 'Off the map' : 'Something broke'}</p>
      <h1 className="font-display text-2xl font-semibold">
        {apiUnreachable
          ? 'The SkillAtlas API is not responding'
          : 'This page could not be loaded'}
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">
        {apiUnreachable
          ? 'Nothing you did caused this — the backend is unreachable. If you are running SkillAtlas locally, check that the API server is still up, then try again.'
          : 'The error has been logged to the console. Trying again often works; if it does not, head back to your dashboard.'}
      </p>
      {error.digest && (
        <p className="font-mono text-xs text-muted-foreground">ref {error.digest}</p>
      )}
      <div className="flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          Try again
        </button>
        <Link
          href="/dashboard"
          className="rounded-md border border-border px-4 py-2 text-sm font-medium focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          Back to dashboard
        </Link>
      </div>
    </main>
  );
}
