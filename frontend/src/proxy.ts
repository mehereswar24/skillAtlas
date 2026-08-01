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

export function proxy(request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  // Everything except API routes, Next internals and static assets.
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)'],
};
