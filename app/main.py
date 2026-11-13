"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_id import RequestIDMiddleware

DESCRIPTION = """
Backend for coordinating airport ground operations: flights, gates & counters, passengers, check-in,
baggage lifecycle & screening, ground staff, tasks, aircraft turnaround, equipment, incidents,
delays, resource allocation, notifications, dashboards, reports and audit logs.

**Auth:** click **Authorize** and log in with email/username + password (OAuth2 password flow).
Default admin: `admin@airportops.com` / `Admin@12345` (change in `.env`).
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=DESCRIPTION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
    )
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["Health"])
    def health():
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_status = "up"
        except Exception:
            db_status = "down"
        finally:
            db.close()
        return {"status": "ok" if db_status == "up" else "degraded", "database": db_status,
                "version": settings.VERSION}

    @app.get("/", include_in_schema=False)
    def root():
        return {"name": settings.PROJECT_NAME, "docs": "/docs", "openapi": f"{settings.API_V1_PREFIX}/openapi.json"}

    return app


app = create_app()
