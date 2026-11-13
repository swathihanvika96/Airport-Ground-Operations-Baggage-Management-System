"""Attach a request id to every request/response and expose it (plus client IP) via contextvars."""
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
client_ip_ctx: ContextVar[str | None] = ContextVar("client_ip", default=None)

HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(HEADER) or uuid.uuid4().hex
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
        t1 = request_id_ctx.set(rid)
        t2 = client_ip_ctx.set(ip)
        request.state.request_id = rid
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(t1)
            client_ip_ctx.reset(t2)
        response.headers[HEADER] = rid
        return response
