import { NextResponse } from 'next/server';

import { apiBaseUrl } from '@/lib/api';
import { setSessionCookies } from '@/lib/session';

/** Creates an account and signs the new user straight in. */
export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.password) {
    return NextResponse.json({ detail: 'Email and password are required' }, { status: 400 });
  }

  const response = await fetch(`${apiBaseUrl()}/api/v1/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: body.email,
      password: body.password,
      display_name: body.display_name ?? null,
    }),
    cache: 'no-store',
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // FastAPI validation failures arrive as a list; flatten to one message.
    const detail = Array.isArray(data.detail)
      ? data.detail.map((d: { msg?: string }) => d.msg ?? '').join('; ')
      : (data.detail ?? 'Unable to create your account');
    return NextResponse.json({ detail }, { status: response.status });
  }

  await setSessionCookies(data);
  return NextResponse.json({ user: data.user }, { status: 201 });
}
