"""Startup schema preparation (``app.core.migrations``).

The API used to run a bare ``create_all`` at startup, which on an unmigrated
database created new tables next to the old ones (e.g. an empty
``applications`` table beside ``workers``) and split the data. These tests
pin the replacement behaviour on the test database.
"""

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from app.core.database import engine
from app.core.migrations import (
    SchemaOutOfDateError,
    _alembic_config,
    head_revision,
    prepare_schema,
)

PREVIOUS_REVISION = "e8a3c6f1b2d9"


def _current_revision() -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _stamp(revision: str) -> None:
    with engine.connect() as conn:
        command.stamp(_alembic_config(conn), revision)
        conn.commit()


@pytest.fixture
def restore_head():
    yield
    _stamp("head")


def test_startup_leaves_the_schema_at_head():
    assert _current_revision() == head_revision()


def test_at_head_is_a_no_op():
    prepare_schema(engine, auto_migrate=False)
    assert _current_revision() == head_revision()


def test_behind_head_is_refused_without_auto_migrate(restore_head):
    _stamp(PREVIOUS_REVISION)
    with pytest.raises(SchemaOutOfDateError, match="alembic upgrade head"):
        prepare_schema(engine, auto_migrate=False)
    # Refusing must not touch the schema.
    assert _current_revision() == PREVIOUS_REVISION


def test_behind_head_is_migrated_with_auto_migrate(restore_head):
    _stamp(PREVIOUS_REVISION)
    prepare_schema(engine, auto_migrate=True)
    assert _current_revision() == head_revision()


def test_unversioned_database_with_tables_is_refused(restore_head):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alembic_version"))
    with pytest.raises(SchemaOutOfDateError, match="no Alembic revision"):
        prepare_schema(engine, auto_migrate=True)


def test_migration_session_settings_do_not_leak_into_the_pool():
    prepare_schema(engine, auto_migrate=False)
    with engine.connect() as conn:
        assert conn.execute(text("SHOW lock_timeout")).scalar() == "0"
