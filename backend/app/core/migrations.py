"""Bring the database schema to the version this code expects, at startup.

Why this exists
---------------
The API used to call ``Base.metadata.create_all()`` on every start. That only
*creates missing tables*; it never checks whether the schema is at the
revision the code was written for. Starting new code on an unmigrated
database therefore created, for example, an empty ``applications`` table next
to the old ``workers`` table, and new rows went into one table while the old
rows sat in the other.

What happens now (all under one PostgreSQL advisory lock, so several API
processes starting together cannot race):

* **Fresh database** (no ``users`` table): create the schema from the models
  and stamp it as the current Alembic head.
* **Managed database behind head**: apply the pending migrations
  (``alembic upgrade head``), or refuse to start with the exact command to run
  when ``DB_AUTO_MIGRATE`` is off.
* **At head**: nothing to migrate. ``create_all`` then only adds tables that
  have no migration yet, which is safe because every rename has been applied.
* **Tables but no Alembic version**: refuse to start. The schema's revision
  cannot be guessed safely; the error explains how to stamp it.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, inspect, text

from app.core.database import Base

# Register every model on Base.metadata; create_all would otherwise see only
# whatever the caller happened to import first.
import app.models  # noqa: E402,F401

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]

#: Arbitrary constant identifying the schema-migration advisory lock.
_LOCK_KEY = 0x52_41_53_43  # "RASC": Resume Analyzer Schema Change

#: Fail fast instead of hanging if another session holds a conflicting lock.
_LOCK_TIMEOUT = "15s"


class SchemaOutOfDateError(RuntimeError):
    """The database schema does not match this code and was not migrated."""


def _alembic_config(connection: Connection) -> Config:
    """Alembic config with absolute paths that runs on ``connection``."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["connection"] = connection
    # Keep the application's logging: alembic.ini's fileConfig would disable
    # every logger that already exists.
    config.attributes["configure_logger"] = False
    return config


def head_revision() -> str | None:
    """The newest migration revision shipped with this code."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def prepare_schema(engine: Engine, *, auto_migrate: bool) -> None:
    """Make the schema match this code, or raise :class:`SchemaOutOfDateError`."""
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": _LOCK_KEY})
        conn.commit()
        try:
            _prepare_locked(conn, auto_migrate=auto_migrate)
        except BaseException:
            conn.rollback()
            raise
        finally:
            # Session-level settings would otherwise stay on the pooled connection.
            conn.execute(text("RESET lock_timeout"))
            conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})
            conn.commit()


def _prepare_locked(conn: Connection, *, auto_migrate: bool) -> None:
    conn.execute(text(f"SET lock_timeout = '{_LOCK_TIMEOUT}'"))
    config = _alembic_config(conn)
    head = ScriptDirectory.from_config(config).get_current_head()

    if not inspect(conn).has_table("users"):
        logger.info("Empty database: creating the schema at revision %s", head)
        Base.metadata.create_all(conn)
        command.stamp(config, "head")
        conn.commit()
        return

    current = MigrationContext.configure(conn).get_current_revision()
    if current is None:
        raise SchemaOutOfDateError(
            "The database has tables but no Alembic revision, so its schema version is "
            "unknown. If it matches this code exactly, run `alembic stamp head`; otherwise "
            "stamp the revision it matches and run `alembic upgrade head`."
        )

    if current != head:
        if not auto_migrate:
            raise SchemaOutOfDateError(
                f"The database schema is at revision {current} but this code expects "
                f"{head}. Run `alembic upgrade head` in backend/ (or set "
                "DB_AUTO_MIGRATE=true) before starting the API."
            )
        logger.warning("Migrating the database schema from %s to %s", current, head)
        command.upgrade(config, "head")

    # At head, so this can only add tables that have no migration yet.
    Base.metadata.create_all(conn)
    conn.commit()
