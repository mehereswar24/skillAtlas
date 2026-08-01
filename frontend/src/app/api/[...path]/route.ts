import { NextRequest, NextResponse } from 'next/server';

import { apiRaw } from '@/lib/api';

/**
 * Catch-all BFF proxy: `/api/<anything>` → `<backend>/api/v1/<anything>`,
 * with the HttpOnly access token attached and refreshed on expiry.
 *
 * Client components therefore call same-origin relative URLs and never see a
 * token, a CORS preflight, or the backend's address. The more specific
 * `/api/auth/*` handlers take precedence over this route.
 */

const HOP_BY_HOP = new Set(['connection', 'keep-alive', 'transfer-encoding', 'upgrade']);

async function proxy(request: NextRequest, segments: string[]) {
  const search = request.nextUrl.search;
  const path = `/api/v1/${segments.join('/')}${search}`;

  const method = request.method;
  const hasBody = method !== 'GET' && method !== 'HEAD';
  const rawBody = hasBody ? await request.text() : undefined;

  const headers = new Headers();
  const contentType = request.headers.get('content-type');
  if (contentType) headers.set('content-type', contentType);
  const accept = request.headers.get('accept');
  if (accept) headers.set('accept', accept);

  let response: Response;
  try {
    // `rawBody` is already-serialised text; `apiRaw` passes string bodies
    // through without re-encoding them.
    response = await apiRaw(path, { method, headers, body: rawBody });
  } catch {
    return NextResponse.json(
      { detail: 'The SkillAtlas API is not reachable. Is the backend running?' },
      { status: 503 },
    );
  }

  // Streamed responses (the AI tutor uses SSE) must be piped, not buffered.
  const responseHeaders = new Headers();
  response.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) responseHeaders.set(key, value);
  });

  return new NextResponse(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}

type Context = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}
export async function POST(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}
export async function PUT(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}
export async function PATCH(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}
export async function DELETE(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}
