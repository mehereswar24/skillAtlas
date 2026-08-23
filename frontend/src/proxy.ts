import { NextResponse, type NextRequest } from 'next/server';

import { ACCESS_COOKIE, REFRESH_COOKIE } from '@/lib/session';

/**
 * Route guard and Content-Security-Policy. (Middleware is called Proxy from
 * Next.js 16 onward.)
 *
 * The guard is an *optimistic* check only: it looks at cookie presence to keep
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

/**
 * Build the CSP for one request, around a freshly generated nonce.
 *
 * This has to live here rather than in `next.config.ts`'s `headers()`, and
 * that is not a style preference. Next.js renders its own inline bootstrap
 * scripts — the RSC payload chunks that `self.__next_f.push(...)` — on every
 * page. A `script-src` without either `'unsafe-inline'` or a nonce blocks
 * them, React never hydrates, and the page dies with
 * `InvariantError: Expected a request ID to be defined for the document via
 * self.__next_r`. Server-rendered markup is still delivered, so the symptom is
 * a page that looks blank rather than one that errors: every framer-motion
 * element is server-rendered at its `hidden` variant (`opacity: 0`) and the
 * hydration that would animate it in never runs.
 *
 * Next picks the nonce up by parsing the `Content-Security-Policy` header off
 * the *request*, so it must be set on both the request and the response.
 * Static `headers()` entries in `next.config.ts` cannot carry a per-request
 * value, which is why the header moved out of there.
 */
function contentSecurityPolicy(
  nonce: string,
  isDev: boolean,
  isSecure: boolean,
): string {
  return [
    "default-src 'self'",
    // Projects run learner code in Pyodide/sql.js workers, which need
    // `wasm-unsafe-eval`. That is deliberately narrower than `unsafe-eval`: it
    // permits WebAssembly compilation and still forbids `eval` of JavaScript.
    //
    // Deliberately *not* `'strict-dynamic'`, which the Next.js guide suggests.
    // Under `strict-dynamic` a CSP3 browser ignores `'self'` entirely and
    // trusts only what the nonced bootstrap loads; the Pyodide worker is built
    // from a `blob:` URL and pulls `/pyodide/pyodide.mjs` in from there, which
    // is exactly the kind of chain that stops being obviously allowed. Keeping
    // host-source `'self'` costs little here — every script this app loads is
    // same-origin, and there is no JSONP-style endpoint to abuse as a gadget.
    //
    // 'unsafe-eval' is dev-only: React uses `eval` to rebuild server error
    // stacks in the browser. Neither React nor Next needs it in production.
    `script-src 'self' 'nonce-${nonce}' 'wasm-unsafe-eval'${isDev ? " 'unsafe-eval'" : ''}`,
    // `'unsafe-inline'` rather than a nonce, and it has to stay that way:
    // framer-motion server-renders its initial variants as inline `style`
    // attributes, which `style-src-attr` inherits from here. A nonce cannot
    // apply to a style attribute, and adding one would make the browser
    // *ignore* `'unsafe-inline'` — so the two cannot be combined.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https://images.unsplash.com",
    "font-src 'self' data:",
    // Workers are constructed from blob: URLs by the Pyodide loader.
    "worker-src 'self' blob:",
    "child-src 'self' blob:",
    // Same-origin only: the BFF proxies everything, so the browser has no
    // reason to reach any other host.
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    // Keyed on the scheme this request actually arrived over, not on
    // NODE_ENV. On https (Vercel, or anything behind a TLS-terminating proxy)
    // it is the right directive and costs nothing, since every URL is already
    // https. Over plain http it is actively destructive: the browser rewrites
    // same-origin navigations to https://, and a production build smoke-tested
    // on http://localhost fails every one of them with ERR_SSL_PROTOCOL_ERROR.
    ...(isSecure ? ['upgrade-insecure-requests'] : []),
  ].join('; ');
}

/** A fresh 128-bit nonce, base64-encoded. `crypto` is a global in the Edge
 *  runtime; `Buffer` is not, so this avoids it. */
function makeNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const signedIn =
    request.cookies.has(ACCESS_COOKIE) || request.cookies.has(REFRESH_COOKIE);

  const nonce = makeNonce();
  // `x-forwarded-proto` is what a TLS-terminating proxy in front of this app
  // sets — Vercel's included. `nextUrl.protocol` is the fallback for a server
  // holding the TLS connection itself.
  const forwarded = request.headers.get('x-forwarded-proto');
  const isSecure = forwarded
    ? forwarded.split(',')[0].trim() === 'https'
    : request.nextUrl.protocol === 'https:';
  const csp = contentSecurityPolicy(
    nonce,
    process.env.NODE_ENV === 'development',
    isSecure,
  );

  if (!signedIn && PROTECTED.some((route) => pathname.startsWith(route))) {
    const login = new URL('/login', request.url);
    // So the learner lands back where they were aiming after signing in.
    login.searchParams.set('next', pathname);
    const redirect = NextResponse.redirect(login);
    redirect.headers.set('Content-Security-Policy', csp);
    return redirect;
  }

  if (signedIn && AUTH_PAGES.some((route) => pathname.startsWith(route))) {
    const redirect = NextResponse.redirect(new URL('/dashboard', request.url));
    redirect.headers.set('Content-Security-Policy', csp);
    return redirect;
  }

  // The request copy is what Next reads the nonce out of when it renders; the
  // `x-nonce` header is how a Server Component can reach it (the root layout
  // passes it to <ThemeScript />, which is hand-written inline script and so
  // is not nonced automatically).
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-nonce', nonce);
  requestHeaders.set('Content-Security-Policy', csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set('Content-Security-Policy', csp);
  return response;
}

export const config = {
  // Everything except API routes, Next internals and static assets.
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)'],
};
