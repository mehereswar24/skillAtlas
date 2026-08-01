import 'server-only';

import { cookies } from 'next/headers';

/**
 * Session handling for the BFF.
 *
 * Tokens live in `HttpOnly` cookies set by our own same-origin route handlers,
 * so browser JavaScript can never read them and an XSS bug cannot exfiltrate a
 * session. Nothing in `src/app/**` outside `src/app/api/**` should import this.
 */

export const ACCESS_COOKIE = 'sa_access';
export const REFRESH_COOKIE = 'sa_refresh';

const isProduction = process.env.NODE_ENV === 'production';

const baseCookie = {
  httpOnly: true,
  // `Secure` cannot be set over plain http, which is how localhost is served.
  secure: isProduction,
  // Lax is enough because the cookie is same-origin: the browser talks to the
  // Next.js server, which is what talks to FastAPI.
  sameSite: 'lax' as const,
  path: '/',
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

export async function setSessionCookies(tokens: TokenPair) {
  const store = await cookies();
  store.set(ACCESS_COOKIE, tokens.access_token, {
    ...baseCookie,
    maxAge: tokens.expires_in,
  });
  store.set(REFRESH_COOKIE, tokens.refresh_token, {
    ...baseCookie,
    maxAge: 60 * 60 * 24 * 7,
  });
}

export async function clearSessionCookies() {
  const store = await cookies();
  store.delete(ACCESS_COOKIE);
  store.delete(REFRESH_COOKIE);
}

export async function getAccessToken(): Promise<string | undefined> {
  return (await cookies()).get(ACCESS_COOKIE)?.value;
}

export async function getRefreshToken(): Promise<string | undefined> {
  return (await cookies()).get(REFRESH_COOKIE)?.value;
}
