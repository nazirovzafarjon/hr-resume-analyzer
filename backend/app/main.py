"""FastAPI application entry point.

Creates the application and wires the routers.
"""
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.routers import auth, dashboard, interviews, jobs, public, users, workers
from app.services.ai.job_analyzer import close_ai_client

logger = logging.getLogger(__name__)

# In DEBUG mode make the app's own INFO-level audit trail (Google exchange,
# user lookup/create) visible on the console without touching uvicorn config.
if settings.DEBUG:
    _app_logger = logging.getLogger("app")
    if not _app_logger.handlers:
        _handler = logging.StreamHandler()
        _handler.setFormatter(
            logging.Formatter("%(levelname)s [%(name)s] %(message)s")
        )
        _app_logger.addHandler(_handler)
        _app_logger.setLevel(logging.INFO)
        _app_logger.propagate = False

_DATABASE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _handle_db_error(request: Request, exc: Exception) -> JSONResponse:
    """Return a clean 503 for database connectivity / operational failures.

    Database unavailability (missing server, missing database, connection
    refused, credentials, etc.) is an environmental condition, not a bug in
    the request. Logging the full traceback is important for operators, while
    the response must never leak ORM/DB internals.
    """
    logger.error("Database connectivity/operational error on %s", request.url, exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "The service is temporarily unavailable. Try again later."},
    )


def _ensure_database() -> None:
    """Create the target database and tables if they do not exist yet.

    MVP bootstrap until the initial Alembic migration is introduced:
    without this a fresh machine gets 'database "resume_analyzer" does
    not exist' and every request fails with a 503.
    """
    from sqlalchemy import text

    database_name = engine.url.database
    if not database_name:
        raise RuntimeError("DATABASE_URL must include a database name")

    if not _DATABASE_NAME_RE.fullmatch(database_name):
        raise RuntimeError(
            "Automatic database creation only supports simple database names "
            "containing letters, numbers, and underscores."
        )

    admin_url = engine.url.set(database="postgres")
    try:
        raw = engine.raw_connection()
        raw.close()
        return  # Database reachable — tables are created below.
    except Exception:  # noqa: BLE001 — raw_connection() raises the raw DBAPI error
        logger.warning("Database %r unreachable, attempting to create it", engine.url.database)

    # Connect to the maintenance database and create the target database.
    try:
        from sqlalchemy import create_engine

        admin_engine = create_engine(admin_url, pool_pre_ping=True)
        with admin_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text(f'CREATE DATABASE "{database_name}"'))
        admin_engine.dispose()
        logger.info("Created database %r", database_name)
    except SQLAlchemyError as exc:
        logger.exception("Could not create database %r", database_name)
        raise RuntimeError(
            f"Database {database_name!r} is unreachable and could not be created. "
            "Check that PostgreSQL is running, credentials are correct, and the "
            "maintenance/template databases are healthy. If PostgreSQL reports a "
            "collation version mismatch, run `ALTER DATABASE postgres REFRESH "
            "COLLATION VERSION;` and `ALTER DATABASE template1 REFRESH COLLATION "
            "VERSION;` as a database superuser."
        ) from exc


def _create_tables_and_seed_superuser() -> None:
    """Create missing tables and seed the first superuser if configured."""
    Base.metadata.create_all(bind=engine)

    from app.crud.user import create_user, has_superuser
    from app.schemas.user import UserCreate

    if not settings.SUPERUSER_EMAIL or not settings.SUPERUSER_PASSWORD:
        return
    db = SessionLocal()
    try:
        if not has_superuser(db):
            create_user(
                db,
                UserCreate(
                    email=settings.SUPERUSER_EMAIL,
                    full_name=settings.SUPERUSER_FULL_NAME,
                    password=settings.SUPERUSER_PASSWORD,
                ),
                is_superuser=True,
            )
            logger.info("Seeded superuser %s", settings.SUPERUSER_EMAIL)
    finally:
        db.close()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _ensure_database()
        _create_tables_and_seed_superuser()
        yield
        await close_ai_client()

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # The Vite dev server (http://localhost:5173) talks to this API from a
    # different origin, so the browser sends a CORS preflight (OPTIONS) before
    # every JSON POST. Allow that origin so preflight requests succeed and the
    # real request is actually sent. Additional origins can be added via the
    # BACKEND_CORS_ORIGINS environment variable (comma-separated).
    cors_origins = [
        origin.strip()
        for origin in settings.BACKEND_CORS_ORIGINS.split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Turn database connectivity/operational failures into a clean 503
    # (with the exception still logged server-side) instead of a 500 that
    # leaks a stack trace / connection internals.
    app.add_exception_handler(SQLAlchemyError, _handle_db_error)

    app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["auth"])
    app.include_router(users.router, prefix=f"{settings.API_PREFIX}/users", tags=["users"])
    app.include_router(jobs.router, prefix=f"{settings.API_PREFIX}/jobs", tags=["jobs"])
    app.include_router(
        workers.router, prefix=f"{settings.API_PREFIX}/workers", tags=["workers"]
    )
    app.include_router(
        public.router, prefix=f"{settings.API_PREFIX}", tags=["public"]
    )
    app.include_router(
        dashboard.router,
        prefix=f"{settings.API_PREFIX}/dashboard",
        tags=["dashboard"],
    )
    app.include_router(
        interviews.router,
        prefix=f"{settings.API_PREFIX}/interviews",
        tags=["interviews"],
    )

    # Serve stored profile images (written under settings.UPLOAD_DIR by the
    # settings service) as plain static files. The directory is created on
    # startup so the mount always has a valid target.
    uploads_dir = Path(settings.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    @app.get("/health", tags=["health"])
    def health_check() -> dict:
        """Basic liveness endpoint."""
        return {"status": "ok"}

    return app


app = create_app()
