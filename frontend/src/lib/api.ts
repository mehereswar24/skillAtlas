import 'server-only';

import { getAccessToken, getRefreshToken, setSessionCookies } from '@/lib/session';

/**
 * Server-side client for the FastAPI backend.
 *
 * Only ever runs on the Next.js server — it reads the HttpOnly access token and
 * transparently refreshes it once on a 401, so a 30-minute access token never
 * surfaces as a random logout.
 */

export const API_BASE_URL = process.env.API_BASE_URL ?? 'http://localhost:8010';

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

  const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: 'no-store',
  });
  if (!response.ok) return undefined;

  const tokens = await response.json();
  await setSessionCookies(tokens);
  return tokens.access_token as string;
}

/** Raw call to the backend, returning the untouched `Response`. */
export async function apiRaw(path: string, init: ApiInit = {}): Promise<Response> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
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

/** Like `api`, but returns `null` instead of throwing on 401/404. */
export async function apiOrNull<T>(path: string, init: ApiInit = {}): Promise<T | null> {
  try {
    return await api<T>(path, init);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 404)) {
      return null;
    }
    throw error;
  }
}
