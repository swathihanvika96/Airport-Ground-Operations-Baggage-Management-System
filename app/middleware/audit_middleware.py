"""Request access log for mutating calls (business-level audit rows are written by services)."""
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("app.access")
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - started) * 1000
        if request.method in MUTATING or response.status_code >= 400:
            logger.info("%s %s -> %s (%.1f ms) rid=%s", request.method, request.url.path, response.status_code,
                        elapsed, getattr(request.state, "request_id", "-"))
        response.headers["X-Process-Time-ms"] = f"{elapsed:.1f}"
        return response
