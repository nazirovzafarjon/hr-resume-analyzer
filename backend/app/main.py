"""FastAPI application entry point.

Creates the application and wires the routers.
"""
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.errors import EMAIL_VERIFICATION_REQUIRED, EmailVerificationRequiredError
from app.core.migrations import prepare_schema
from app.core.request_context import REQUEST_ID_HEADER, RequestContextMiddleware, request_id_from_scope
from app.routers import admin, applications, auth, candidate, dashboard, exports, interviews, jobs, public, users
from app.services.admin import errors as error_monitor
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


def _record_error(request: Request, status_code: int, exc: BaseException, message: str) -> str | None:
    """Store a 5xx for the admin System Errors page; returns the request id."""
    request_id = request_id_from_scope(request.scope)
    error_monitor.record_error(
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        error_type=type(exc).__name__,
        message=message,
        request_id=request_id,
        user_id=error_monitor.user_id_from_authorization(request.headers.get("authorization")),
    )
    return request_id


def _handle_db_error(request: Request, exc: Exception) -> JSONResponse:
    """Return a clean 503 for database connectivity / operational failures.

    Database unavailability (missing server, missing database, connection
    refused, credentials, etc.) is an environmental condition, not a bug in
    the request. Logging the full traceback is important for operators, while
    the response must never leak ORM/DB internals.
    """
    logger.error("Database connectivity/operational error on %s", request.url, exc_info=exc)
    # The recorded message is the exception class only: SQLAlchemy messages
    # quote SQL and bound parameters, which may contain user data.
    _record_error(request, 503, exc, "Database error")
    return JSONResponse(
        status_code=503,
        content={"detail": "The service is temporarily unavailable. Try again later."},
    )


async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Record deliberate 5xx responses (e.g. AI provider outages), then answer as usual."""
    if exc.status_code >= 500:
        # Sync DB write: keep it off the event loop.
        await run_in_threadpool(_record_error, request, exc.status_code, exc, str(exc.detail))
    return await http_exception_handler(request, exc)


async def _handle_email_verification_required(
    request: Request, exc: EmailVerificationRequiredError
) -> JSONResponse:
    """Answer a panel request from an unverified account with a coded 403.

    The ``code`` lets the frontend show the "verify your email" UI instead of a
    generic Forbidden message.
    """
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc), "code": EMAIL_VERIFICATION_REQUIRED},
    )


def _report_unhandled_error(scope: dict, exc: Exception) -> None:
    """Store an unhandled exception (called by RequestContextMiddleware)."""
    _record_error(Request(scope), 500, exc, str(exc))


def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort response for unhandled exceptions (non-DEBUG mode).

    The traceback goes to the server log only; the client gets a generic
    message plus the request id to quote when reporting the problem. The error
    itself was already recorded by RequestContextMiddleware. Starlette
    re-raises the exception after this response, so it is still logged by the
    server (and surfaced by the test client).
    """
    request_id = request_id_from_scope(request.scope)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
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


def _warn_if_insecure_configuration() -> None:
    """Warn (never fail) at startup about production-unsafe settings.

    Only variable *names* and statuses are logged — never a secret value. A
    missing or default signing key, or DEBUG left on, are reported so a
    misconfigured deployment is visible in the logs immediately.
    """
    weak_secrets = {"", "change-me-in-production", "dev-secret-change-me"}
    if settings.SECRET_KEY in weak_secrets or len(settings.SECRET_KEY) < 32:
        if settings.DEBUG:
            logger.info(
                "SECRET_KEY is a development value; set a strong random value for production."
            )
        else:
            logger.warning(
                "SECRET_KEY is missing, default, or too short while DEBUG is off. "
                "Set a strong random SECRET_KEY before serving production traffic."
            )
    if settings.DEBUG:
        logger.info("DEBUG is enabled; disable it in production.")


def _warn_if_sandbox_sender() -> None:
    """Warn when the Resend sandbox sender is still configured.

    ``onboarding@resend.dev`` only delivers to the address that owns the Resend
    account, so any other recipient is rejected with a 403. A verified custom
    domain is required for real users.
    """
    if settings.EMAIL_FROM.strip().lower().endswith("@resend.dev"):
        logger.warning(
            "EMAIL_FROM still uses the Resend sandbox sender (@resend.dev). "
            "It can only deliver to your own Resend account address. Verify a "
            "domain (e.g. edubaselearning.uz) and set EMAIL_FROM to a sender on it."
        )


def _cleanup_expired_pending() -> None:
    """Best-effort purge of old pending registrations at startup.

    Keeps ``pending_registrations`` from growing unbounded. A failure here must
    never stop the API from starting.
    """
    from app.services.auth import cleanup_expired_pending

    db = SessionLocal()
    try:
        removed = cleanup_expired_pending(db)
        if removed:
            logger.info("Purged %s expired/consumed pending registration(s)", removed)
    except Exception:  # noqa: BLE001 — startup must not fail on housekeeping
        logger.warning("Pending-registration cleanup failed", exc_info=True)
    finally:
        db.close()


def _prepare_schema_and_seed_superuser() -> None:
    """Bring the schema to this code's revision, then ensure the configured superuser.

    ``prepare_schema`` creates a fresh database or applies pending Alembic
    migrations (see ``app.core.migrations`` for why a bare ``create_all`` is
    not enough). See ``app.services.admin.users.ensure_configured_superuser``
    for exactly what the ``SUPERUSER_*`` settings do.
    """
    prepare_schema(engine, auto_migrate=settings.DB_AUTO_MIGRATE)

    if not settings.SUPERUSER_EMAIL:
        return

    from app.services.admin.users import ensure_configured_superuser

    db = SessionLocal()
    try:
        ensure_configured_superuser(
            db,
            email=settings.SUPERUSER_EMAIL,
            password=settings.SUPERUSER_PASSWORD,
            full_name=settings.SUPERUSER_FULL_NAME,
        )
    finally:
        db.close()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _warn_if_insecure_configuration()
        _warn_if_sandbox_sender()
        _ensure_database()
        _prepare_schema_and_seed_superuser()
        _cleanup_expired_pending()
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
        # Lets the frontend read the id it can show next to an error message.
        expose_headers=["X-Request-ID"],
    )

    # Turn database connectivity/operational failures into a clean 503
    # (with the exception still logged server-side) instead of a 500 that
    # leaks a stack trace / connection internals.
    app.add_exception_handler(SQLAlchemyError, _handle_db_error)
    app.add_exception_handler(
        EmailVerificationRequiredError, _handle_email_verification_required
    )
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)

    # Added last so it wraps everything above: every response (including
    # CORS preflights and errors) carries an X-Request-ID.
    app.add_middleware(RequestContextMiddleware, on_unhandled_error=_report_unhandled_error)

    app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["auth"])
    app.include_router(users.router, prefix=f"{settings.API_PREFIX}/users", tags=["users"])
    app.include_router(jobs.router, prefix=f"{settings.API_PREFIX}/jobs", tags=["jobs"])
    app.include_router(
        applications.router, prefix=f"{settings.API_PREFIX}/applications", tags=["applications"]
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
    app.include_router(
        exports.router,
        prefix=f"{settings.API_PREFIX}",
        tags=["exports"],
    )
    # Candidate Portal: separate identity and tokens (see routers/candidate.py).
    app.include_router(
        candidate.router,
        prefix=f"{settings.API_PREFIX}/candidate",
        tags=["candidate portal"],
    )
    app.include_router(
        admin.router,
        prefix=f"{settings.API_PREFIX}/admin",
        tags=["admin (superuser only)"],
    )

    # Serve stored profile images (UPLOAD_DIR/profile, written by the settings
    # service) as plain static files. Only that sub-directory is public:
    # candidates' CVs (UPLOAD_DIR/resumes) are served exclusively through the
    # authenticated GET /api/applications/{id}/resume. The directory is created on
    # startup so the mount always has a valid target.
    profile_dir = Path(settings.UPLOAD_DIR) / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads/profile", StaticFiles(directory=profile_dir), name="uploads")

    @app.get("/health", tags=["health"])
    def health_check() -> dict:
        """Basic liveness endpoint."""
        return {"status": "ok"}

    return app


app = create_app()
