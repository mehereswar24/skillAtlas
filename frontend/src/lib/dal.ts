import 'server-only';

import { cache } from 'react';
import { redirect } from 'next/navigation';

import { apiOrNull } from '@/lib/api';
import { getAccessToken, getRefreshToken } from '@/lib/session';
import type { User } from '@/lib/types';

/**
 * Data Access Layer for the session.
 *
 * Server Components call `getCurrentUser()` rather than reading cookies
 * directly, so authorization lives in one place. `cache()` deduplicates the
 * `/auth/me` call within a single render pass — a page and three components
 * asking for the user costs one request.
 *
 * Read this in the leaf that needs it, not at the top of a layout: awaiting it
 * in a layout holds `{children}` behind the request and delays the first
 * streamed chunk.
 */
export const getCurrentUser = cache(async (): Promise<User | null> => {
  return apiOrNull<User>('/api/v1/auth/me');
});

/**
 * Require a signed-in user, or bounce to login with a return path.
 *
 * When a session cookie is present but does not resolve to a user — expired,
 * revoked, or issued by a different SECRET_KEY — redirecting straight to
 * `/login` would loop: the Proxy sees the cookie, decides you are signed in,
 * and sends you back here. Routing through the logout handler drops the stale
 * cookie first, so the next request is unambiguously signed out.
 */
export async function requireUser(returnTo?: string): Promise<User> {
  const user = await getCurrentUser();
  if (user) return user;

  const next = returnTo ?? '/dashboard';
  const hasCookie = (await getAccessToken()) || (await getRefreshToken());
  // A stale cookie has to be cleared by a Route Handler before we land on
  // /login, or the optimistic Proxy check bounces us straight back here.
  redirect(
    hasCookie
      ? `/api/auth/logout?next=${encodeURIComponent(next)}`
      : `/login?next=${encodeURIComponent(next)}`,
  );
}
