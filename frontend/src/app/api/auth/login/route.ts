import { NextResponse } from 'next/server';

import { API_BASE_URL } from '@/lib/api';
import { setSessionCookies } from '@/lib/session';

/**
 * Exchanges credentials for a session cookie.
 *
 * The tokens are deliberately not returned to the browser — they go straight
 * into HttpOnly cookies and never touch client JavaScript.
 */
export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.password) {
    return NextResponse.json({ detail: 'Email and password are required' }, { status: 400 });
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: body.email, password: body.password }),
    cache: 'no-store',
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return NextResponse.json(
      { detail: data.detail ?? 'Unable to sign in' },
      { status: response.status },
    );
  }

  await setSessionCookies(data);
  return NextResponse.json({ user: data.user });
}
