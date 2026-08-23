"""Security response headers.

These are the API's own headers. The browser talks to the Next BFF, not to this
service, so the headers that matter for rendered pages are set there
(`frontend/next.config.ts`); these protect the API surface itself and anything
that reaches it directly.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

# A JSON API renders nothing, so the policy can be maximally restrictive: no
# scripts, no frames, no embedded anything. This matters because a browser
# asked to render an API error page must not execute anything reflected in it.
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

BASE_HEADERS = {
    # Stop a browser second-guessing Content-Type and executing JSON as script.
    "X-Content-Type-Options": "nosniff",
    # Legacy, but free, and still honoured by some embedded browsers.
    "X-Frame-Options": "DENY",
    # Do not leak the path of an internal API call to third parties.
    "Referrer-Policy": "no-referrer",
    # Nothing here needs hardware or location access.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    "Content-Security-Policy": API_CSP,
    # Responses are user-specific and must never land in a shared cache.
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach hardening headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        for header, value in BASE_HEADERS.items():
            # `setdefault` semantics: a route that has deliberately chosen its
            # own caching or policy keeps it.
            if header not in response.headers:
                response.headers[header] = value

        # HSTS only in production, and only over TLS. Sending it from a local
        # http:// server would pin the browser to https for localhost and break
        # every other project on port 3000.
        if settings.is_production and request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response
