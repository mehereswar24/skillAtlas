import { NextResponse, type NextRequest } from 'next/server';

import { clearSessionCookies } from '@/lib/session';

/** Sign out from the user menu. */
export async function POST() {
  await clearSessionCookies();
  return NextResponse.json({ ok: true });
}

/**
 * Clear the session and continue to `?next=`.
 *
 * This exists to break a redirect loop. The Proxy guard is optimistic — it only
 * checks that a session cookie is *present* — so an expired or otherwise
 * invalid cookie makes it treat you as signed in. It then sends you from
 * `/login` to `/dashboard`, the page resolves the session for real, finds
 * nobody, and sends you back to `/login`, forever.
 *
 * A Server Component cannot delete a cookie mid-render, but a Route Handler
 * can. So `requireUser` routes through here when a cookie exists but resolves
 * to no user: the stale cookie is dropped, and the redirect that follows
 * arrives at `/login` with no session for the Proxy to misread.
 */
export async function GET(request: NextRequest) {
  await clearSessionCookies();

  const next = request.nextUrl.searchParams.get('next');
  // Only same-origin relative paths, so this cannot be used as an open redirect.
  const destination = next && next.startsWith('/') && !next.startsWith('//') ? next : '/';

  return NextResponse.redirect(new URL(destination, request.url));
}
