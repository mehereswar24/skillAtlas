import Link from 'next/link';

/**
 * Every `notFound()` in the app — an unknown company, concept, project,
 * portfolio handle, or simply a mistyped URL — landed on Next's built-in
 * black-and-white 404, which shares nothing with the rest of the product and
 * offers no way back. This is the app's own.
 */
export default function NotFound() {
  return (
    <main className="flex min-h-[60vh] flex-col items-center justify-center gap-5 px-6 py-24 text-center">
      <p className="eyebrow">404 — off the edge of the map</p>
      <h1 className="font-display text-2xl font-semibold">There is nothing here</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        The page you asked for does not exist. It may have been renamed, or the link that
        brought you here may be out of date.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/explore"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          Explore the atlas
        </Link>
        <Link
          href="/dashboard"
          className="rounded-md border border-border px-4 py-2 text-sm font-medium focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          Your dashboard
        </Link>
      </div>
    </main>
  );
}
