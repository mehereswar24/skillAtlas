"""Request logging with a correlation id.

One line per request, carrying the id, method, path, status and duration. The
id is generated at the edge if the caller did not supply one and returned as
`X-Request-ID`, so a user reporting "it failed at 14:32" can be found in the
log by a single value rather than by guessing from timestamps.

Format follows the environment: JSON lines in production so a log shipper can
parse them, human-readable locally.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

logger = logging.getLogger("skillatlas.request")

# Readable by any log call during the request, so a handler deep in a service
# can attach the id without it being threaded through every signature.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Paths whose every hit is a health probe. Logging them buries real traffic.
QUIET_PATHS = ("/health", "/health/ready")


def current_request_id() -> str:
    return request_id_var.get()


class JsonFormatter(logging.Formatter):
    """Render a record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", current_request_id()),
        }
        for key in ("method", "path", "status", "duration_ms", "client"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Install one stdout handler on the root logger.

    Containers expect logs on stdout; writing to a file inside one just fills
    the layer. Existing handlers are replaced rather than added to, so repeated
    calls (reload, tests) do not duplicate every line.
    """
    handler = logging.StreamHandler()
    if settings.json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(levelname)-8s %(name)s  %(message)s")
        )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    # uvicorn duplicates access logs in its own format; ours already carries
    # the same information plus the request id.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Assign a request id, time the request, log the outcome."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get("x-request-id", "")
        # Bound and sanitised: this value is echoed into a header and into
        # logs, and it arrives from the client.
        request_id = (
            "".join(c for c in incoming if c.isalnum() or c in "-_")[:64]
            or uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "unhandled error",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "duration_ms": duration_ms,
                },
            )
            # The traceback is logged, never returned: in production it would
            # hand an attacker the stack, and `debug` is forced off there anyway.
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error.",
                    "request_id": request_id,
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        if not request.url.path.startswith(QUIET_PATHS):
            logger.log(
                logging.WARNING if response.status_code >= 500 else logging.INFO,
                "%s %s -> %s",
                request.method,
                request.url.path,
                response.status_code,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        return response
