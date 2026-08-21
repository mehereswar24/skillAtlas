import { NextRequest, NextResponse } from 'next/server';

import { API_BASE_URL } from '@/lib/api';

/**
 * BFF route for the anonymous helper.
 *
 * It exists as its own handler rather than going through `/api/[...path]` for
 * two reasons, both of them security rather than convenience:
 *
 * 1. **No token.** The catch-all attaches the session's access token to every
 *    call. This endpoint must be anonymous even for a signed-in visitor, so
 *    nothing user-scoped can be reached through a door that is rate-limited as
 *    though nobody were behind it.
 *
 * 2. **The caller's address.** Every request to FastAPI originates from this
 *    Next.js server, so without forwarding, the API's per-IP rate limit would
 *    see one client — localhost — and every visitor would share a bucket. Next
 *    removed `NextRequest.ip` in 15, so the address comes from the headers a
 *    front proxy set, falling back to the socket address Node exposes.
 *
 * The API treats `X-Forwarded-For` as a hint, not a fact: it also enforces a
 * global ceiling that a forged header cannot get past.
 */

function clientAddress(request: NextRequest): string | null {
  const forwarded = request.headers.get('x-forwarded-for');
  if (forwarded) return forwarded.split(',')[0]?.trim() || null;
  return request.headers.get('x-real-ip')?.trim() || null;
}

export async function POST(request: NextRequest) {
  const headers = new Headers({ 'content-type': 'application/json' });
  const address = clientAddress(request);
  if (address) headers.set('x-forwarded-for', address);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/chat/public`, {
      method: 'POST',
      headers,
      body: await request.text(),
      cache: 'no-store',
    });
  } catch {
    return NextResponse.json(
      { detail: 'The SkillAtlas API is not reachable. Is the backend running?' },
      { status: 503 },
    );
  }

  // The answer is an SSE stream, so the body is piped rather than buffered.
  const out = new Headers();
  for (const key of ['content-type', 'cache-control', 'retry-after']) {
    const value = response.headers.get(key);
    if (value) out.set(key, value);
  }

  return new NextResponse(response.body, { status: response.status, headers: out });
}
