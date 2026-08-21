import { NextResponse, type NextRequest } from 'next/server';

import { ACCESS_COOKIE, REFRESH_COOKIE } from '@/lib/session';

/**
 * Route guard. (Middleware is called Proxy from Next.js 16 onward.)
 *
 * This is an *optimistic* check only: it looks at cookie presence to keep
 * signed-out visitors out of the app shell, and does no network or database
 * work, because Proxy runs on every request including prefetches. The real
 * authorization happens in the API on every call — a forged cookie gets past
 * this and straight into a 401.
 */

/** Routes that only make sense for a signed-in learner.
 *
 * Keep this in step with the pages that call `requireUser`. Those redirect on
 * their own; catching it here just saves a doomed `/auth/me` round trip. */
const PROTECTED = [
  '/dashboard',
  '/roadmap',
  '/projects',
  '/community',
  '/companies',
  '/concepts',
];

/** Auth pages a signed-in learner has no reason to see again. */
const AUTH_PAGES = ['/login', '/signup'];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const signedIn =
    request.cookies.has(ACCESS_COOKIE) || request.cookies.has(REFRESH_COOKIE);

  if (!signedIn && PROTECTED.some((route) => pathname.startsWith(route))) {
    const login = new URL('/login', request.url);
    // So the learner lands back where they were aiming after signing in.
    login.searchParams.set('next', pathname);
    return NextResponse.redirect(login);
  }

  if (signedIn && AUTH_PAGES.some((route) => pathname.startsWith(route))) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Everything except API routes, Next internals and static assets.
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)'],
};
