import 'server-only';

import { getAccessToken, getRefreshToken, setSessionCookies } from '@/lib/session';

/**
 * Server-side client for the FastAPI backend.
 *
 * Only ever runs on the Next.js server — it reads the HttpOnly access token and
 * transparently refreshes it once on a 401, so a 30-minute access token never
 * surfaces as a random logout.
 */

/**
 * Where the FastAPI backend lives, as seen from the Next.js server.
 *
 * A function rather than a module-level constant, and that is load-bearing on
 * Vercel. The API runs as a private second service and its URL arrives through
 * a service binding, which Vercel injects **at runtime only** — bindings do not
 * resolve during builds. Resolving this eagerly at import time would therefore
 * throw during `next build`, before the variable it is complaining about could
 * possibly exist.
 *
 * The localhost default is a development convenience and must not survive into
 * production. Unset on a hosted deployment, it would leave every server render
 * quietly dialling a port on the rendering host itself: not a failure at boot,
 * but a 500 on each data-backed page once real traffic arrives, and only then.
 * Throwing on first use turns that into one legible error instead.
 */
export function apiBaseUrl(): string {
  const configured = process.env.API_BASE_URL;
  if (configured) return configured.replace(/\/+$/, '');
  if (process.env.NODE_ENV === 'production') {
    throw new Error(
      'API_BASE_URL is not set. The Next.js server needs the address of the ' +
        'FastAPI backend. On Vercel this comes from the `api` service binding ' +
        'declared in vercel.json; elsewhere set it to the API origin, for ' +
        'example https://api.example.com.',
    );
  }
  return 'http://localhost:8010';
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

type ApiInit = Omit<RequestInit, 'body'> & { body?: unknown };

function buildInit(init: ApiInit, token?: string): RequestInit {
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return {
    ...init,
    headers,
    // A string body is already serialised — the catch-all proxy forwards the
    // client's raw payload and must not double-encode it.
    body:
      init.body === undefined
        ? undefined
        : typeof init.body === 'string'
          ? init.body
          : JSON.stringify(init.body),
    // Never cache authenticated data; correctness beats a cache hit here.
    cache: 'no-store',
  };
}

/** Exchange the refresh token for a new pair. Returns the new access token. */
async function refreshAccessToken(): Promise<string | undefined> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return undefined;

  const response = await fetch(`${apiBaseUrl()}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: 'no-store',
  });
  if (!response.ok) return undefined;

  const tokens = await response.json();

  // Persisting is best-effort: Next only allows cookie writes from a Server
  // Action or Route Handler, and this also runs during Server Component
  // renders, where the write throws. The fresh access token is returned either
  // way, so the render succeeds — it just is not saved. Requests through the
  // BFF proxy route (`/api/[...path]`) are Route Handlers and do persist it,
  // which is where the great majority of calls go.
  try {
    await setSessionCookies(tokens);
  } catch {
    // Read-only cookie context. Nothing to do but carry on with the token.
  }

  return tokens.access_token as string;
}

/** Raw call to the backend, returning the untouched `Response`. */
export async function apiRaw(path: string, init: ApiInit = {}): Promise<Response> {
  const url = `${apiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`;
  const token = await getAccessToken();

  let response = await fetch(url, buildInit(init, token));

  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      response = await fetch(url, buildInit(init, refreshed));
    }
  }
  return response;
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
    // FastAPI validation errors arrive as a list of {loc, msg, type}.
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? '').join('; ');
    }
    return response.statusText;
  } catch {
    return response.statusText;
  }
}

/** Call the backend and parse JSON, throwing `ApiError` on failure. */
export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const response = await apiRaw(path, init);
  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Like `api`, but returns `null` instead of throwing for the failures a page
 * is expected to survive: not signed in, not found, or throttled.
 *
 * 429 belongs in that list for the same reason the other two do. Pages call
 * this for optional panels, several in one `Promise.all`; a server component
 * that throws takes the whole route down to a 500 error page. Losing one panel
 * to a rate limit is a degraded page, which is the point of this helper —
 * losing the route is not. This is not hypothetical: `GET /resume/uploads` was
 * being charged to the hourly *upload* budget, so around thirty views of
 * /resume in an hour turned it into a 500.
 */
export async function apiOrNull<T>(path: string, init: ApiInit = {}): Promise<T | null> {
  try {
    return await api<T>(path, init);
  } catch (error) {
    if (
      error instanceof ApiError &&
      (error.status === 401 || error.status === 404 || error.status === 429)
    ) {
      return null;
    }
    throw error;
  }
}
