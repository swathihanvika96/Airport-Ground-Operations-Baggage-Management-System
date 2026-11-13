"""Centralised exception handling -> consistent JSON error envelope."""
import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException

logger = logging.getLogger("app.errors")


def _body(request: Request, code: str, message: str, details=None) -> dict:
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
        "request_id": getattr(request.state, "request_id", None),
        "path": request.url.path,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(status_code=exc.status_code, headers=headers,
                            content=jsonable_encoder(_body(request, exc.code, exc.message, exc.details)))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"],
                    "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422,
                            content=jsonable_encoder(_body(request, "VALIDATION_ERROR", "Request validation failed", details)))

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        code = "UNAUTHORIZED" if exc.status_code == 401 else f"HTTP_{exc.status_code}"
        return JSONResponse(status_code=exc.status_code, headers=getattr(exc, "headers", None),
                            content=_body(request, code, str(exc.detail)))

    @app.exception_handler(IntegrityError)
    async def integrity_handler(request: Request, exc: IntegrityError):
        logger.warning("Integrity error: %s", exc.orig)
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content=_body(request, "INTEGRITY_ERROR",
                                          "The operation conflicts with existing data (duplicate or invalid reference)"))

    @app.exception_handler(OperationalError)
    async def db_unavailable_handler(request: Request, exc: OperationalError):
        logger.error("Database error: %s", exc)
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content=_body(request, "DATABASE_UNAVAILABLE", "Database is unavailable"))

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_handler(request: Request, exc: SQLAlchemyError):
        logger.exception("Database error")
        return JSONResponse(status_code=500, content=_body(request, "DATABASE_ERROR", "A database error occurred"))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error")
        return JSONResponse(status_code=500, content=_body(request, "INTERNAL_ERROR", "An unexpected error occurred"))
