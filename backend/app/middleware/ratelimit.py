"""In-process rate limiting.

A fixed set of buckets keyed by client and route class, using the token-bucket
algorithm — a sustained rate plus a burst allowance, because real traffic is
bursty and a limiter that forbids all bursts rejects legitimate users.

**Scope, stated plainly.** State lives in this process, so N replicas enforce N
times the configured limit. That is the correct trade for a single-container
deployment and is wrong for a horizontally scaled one; the fix there is a shared
counter in Redis, and `_Bucket` is deliberately small enough to swap out. What
this does buy, today, is that a login endpoint cannot be brute-forced and the
Ollama tutor cannot be turned into someone else's free GPU.

Limits are applied per route *class* rather than per path, because the thing
worth protecting differs by kind: credentials, expensive inference, uploads,
and everything else.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

# Route classes, matched against the request path in order. The first prefix
# that matches wins, so put the specific ones first.
AUTH_PATHS = (
    "/api/v1/auth/login",
    "/api/v1/auth/signup",
    "/api/v1/auth/refresh",
)
TUTOR_PATHS = ("/api/v1/chat",)
UPLOAD_PATHS = ("/api/v1/resume/uploads",)
# ...but only for the methods that actually ingest a file. The upload budget is
# hourly and small because parsing a PDF is expensive; `GET /uploads` merely
# lists them, and the résumé page reads it on *every render*. Charging that
# read to the write budget meant ~30 page views an hour exhausted it, after
# which /resume returned 500 rather than a page. Reads fall through to the
# default per-minute class, which is what they always should have used.
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH"})

# Never limited: liveness and readiness probes come from the orchestrator on
# every interval, and rate-limiting them causes the restart loop they exist to
# prevent.
#
# Split by match kind on purpose. "/" has to be an *exact* match — as a prefix
# it matches every path there is, which silently exempts the entire API and
# turns this middleware into a no-op.
EXEMPT_PREFIXES = ("/health",)
EXEMPT_EXACT = frozenset({"/", "/docs", "/redoc", "/openapi.json"})


@dataclass
class _Bucket:
    """One client's allowance for one route class.

    `tokens` refills at `rate` per second up to `capacity`. Storing the last
    refill time rather than ticking on a timer means an idle bucket costs
    nothing until it is next touched.
    """

    tokens: float
    capacity: float
    rate: float
    updated: float

    def take(self, now: float) -> tuple[bool, float]:
        """Spend one token. Returns (allowed, seconds until next token)."""
        elapsed = now - self.updated
        self.updated = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= 1:
            self.tokens -= 1
            return True, 0.0
        return False, (1 - self.tokens) / self.rate if self.rate else 60.0


@dataclass
class _Limiter:
    """`allowance` requests per `period_seconds`.

    The period is explicit rather than assumed to be a minute, because the
    upload budget is naturally hourly and expressing it as "requests per
    minute" rounds 30/hour down to zero.
    """

    allowance: int
    period_seconds: float = 60.0
    buckets: dict[str, _Bucket] = field(default_factory=dict)

    def check(self, key: str, now: float) -> tuple[bool, float]:
        bucket = self.buckets.get(key)
        if bucket is None:
            # Burst equal to the full allowance: a page that fires six requests
            # on load must not trip a limit meant for abuse.
            bucket = _Bucket(
                tokens=float(self.allowance),
                capacity=float(self.allowance),
                rate=self.allowance / self.period_seconds,
                updated=now,
            )
            self.buckets[key] = bucket
        return bucket.take(now)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket limiting per client address and route class."""

    # Buckets are only dropped when the table grows past this, so a long-lived
    # process cannot accumulate one entry per address seen since boot.
    MAX_TRACKED = 50_000

    def __init__(self, app):
        super().__init__(app)
        self._lock = Lock()
        self._limiters = {
            "auth": _Limiter(settings.rate_limit_auth_per_minute),
            "tutor": _Limiter(settings.rate_limit_tutor_per_minute),
            # Hourly: an upload is slow and costly, and the honest budget for
            # one is "a few an hour", not a fraction of a request per minute.
            "upload": _Limiter(settings.rate_limit_upload_per_hour, 3600.0),
            "default": _Limiter(settings.rate_limit_default_per_minute),
        }

    def _client_key(self, request: Request) -> str:
        """Identify the caller.

        `X-Forwarded-For` is only consulted when `TRUST_PROXY_HEADERS` says
        something we control sets it. Trusting it unconditionally lets any
        client pick its own identity and makes every limit here decorative.
        """
        if settings.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                # Left-most entry is the original client; the rest are proxies.
                return forwarded.split(",")[0].strip()
        client = request.client
        return client.host if client else "unknown"

    @staticmethod
    def _route_class(path: str, method: str = "GET") -> str | None:
        if path in EXEMPT_EXACT or path.startswith(EXEMPT_PREFIXES):
            return None
        if path.startswith(AUTH_PATHS):
            return "auth"
        if path.startswith(TUTOR_PATHS):
            return "tutor"
        if path.startswith(UPLOAD_PATHS) and method.upper() in WRITE_METHODS:
            return "upload"
        return "default"

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        route_class = self._route_class(request.url.path, request.method)
        if route_class is None:
            return await call_next(request)

        key = f"{route_class}:{self._client_key(request)}"
        now = time.monotonic()

        with self._lock:
            limiter = self._limiters[route_class]
            if len(limiter.buckets) > self.MAX_TRACKED:
                # Drop buckets that have refilled completely: they are
                # indistinguishable from a client that has never been seen.
                limiter.buckets = {
                    bucket_key: bucket
                    for bucket_key, bucket in limiter.buckets.items()
                    if bucket.tokens < bucket.capacity
                }
            allowed, retry_after = limiter.check(key, now)
            remaining = int(limiter.buckets[key].tokens)
            limit = limiter.allowance

        if not allowed:
            # 429 with Retry-After, not 500: a well-written client paces itself
            # off this rather than discovering the limit by hitting it again.
            seconds = max(1, int(retry_after + 0.999))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down and retry.",
                    "retry_after_seconds": seconds,
                },
                headers={
                    "Retry-After": str(seconds),
                    "RateLimit-Limit": str(limit),
                    "RateLimit-Remaining": "0",
                    "RateLimit-Reset": str(seconds),
                },
            )

        response = await call_next(request)
        response.headers["RateLimit-Limit"] = str(limit)
        response.headers["RateLimit-Remaining"] = str(remaining)
        return response
