"""rename workers to applications

A ``workers`` row was always one job application (it becomes a "candidate"
once ``candidate_at`` is set), so the table, its references and the batch
bookkeeping columns now say so:

* ``workers`` -> ``applications`` (plus its sequence, primary key, index and
  foreign key names)
* ``application_responses.worker_id`` -> ``application_id``
* ``ai_analysis_runs.worker_id`` -> ``application_id``
* ``analysis_batches.worker_ids`` / ``current_worker_id`` ->
  ``application_ids`` / ``current_application_id``

Pure renames: no data is copied or changed. Idempotent like the previous
revisions. If the API was started on the new code before this migration ran,
its startup ``create_all`` made an empty ``applications`` table next to
``workers``; that empty table is dropped first. If both tables hold rows the
migration stops instead of guessing.

Revision ID: 2cb0c8660dbf
Revises: e8a3c6f1b2d9
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2cb0c8660dbf"
down_revision: Union[str, None] = "e8a3c6f1b2d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, old column, new column)
_COLUMNS = [
    ("application_responses", "worker_id", "application_id"),
    ("ai_analysis_runs", "worker_id", "application_id"),
    ("analysis_batches", "worker_ids", "application_ids"),
    ("analysis_batches", "current_worker_id", "current_application_id"),
]

# Tables whose constraint names mention the old table/columns. Constraint
# names are rewritten generically so the result matches a fresh create_all,
# including the named NOT NULL constraints newer PostgreSQL versions keep
# (e.g. ``workers_name_not_null``), primary and foreign keys.
_CONSTRAINT_TABLES = ["application_responses", "ai_analysis_runs", "analysis_batches"]

# (old index, new index) for plain indexes (constraint-backed ones follow
# their constraint)
_INDEXES = [
    ("ix_workers_job_id", "ix_applications_job_id"),
    ("ix_application_responses_worker_id", "ix_application_responses_application_id"),
]

_SEQUENCES = [("workers_id_seq", "applications_id_seq")]


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _constraint_names(table: str) -> list[str]:
    return list(
        op.get_bind()
        .execute(
            sa.text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = to_regclass(:table) ORDER BY conname"
            ),
            {"table": table},
        )
        .scalars()
    )


def _constraint_rename(name: str, forward: bool) -> str:
    if forward:
        if name.startswith("workers_"):
            name = "applications_" + name[len("workers_"):]
        return name.replace("worker_id", "application_id")
    if name.startswith("applications_"):
        name = "workers_" + name[len("applications_"):]
    return name.replace("application_id", "worker_id")


def _rename_all(forward: bool) -> None:
    """Rename columns, constraints, indexes and sequences in either direction."""
    for table, old, new in _COLUMNS:
        source, target = (old, new) if forward else (new, old)
        if source in _columns(table) and target not in _columns(table):
            op.alter_column(table, source, new_column_name=target)

    main_table = "applications" if forward else "workers"
    for table in [main_table, *_CONSTRAINT_TABLES]:
        existing = _constraint_names(table)
        for name in existing:
            target = _constraint_rename(name, forward)
            if target != name and target not in existing:
                op.execute(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{name}" TO "{target}"')

    for old, new in _INDEXES:
        source, target = (old, new) if forward else (new, old)
        op.execute(f'ALTER INDEX IF EXISTS "{source}" RENAME TO "{target}"')

    for old, new in _SEQUENCES:
        source, target = (old, new) if forward else (new, old)
        op.execute(f'ALTER SEQUENCE IF EXISTS "{source}" RENAME TO "{target}"')


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "workers" in tables:
        if "applications" in tables:
            rows = bind.execute(sa.text("SELECT count(*) FROM applications")).scalar()
            if rows:
                raise RuntimeError(
                    "Both 'workers' and 'applications' contain rows. The API probably ran on "
                    "the new code before this migration and accepted new applications; merge "
                    "them by hand, then re-run the migration."
                )
            op.drop_table("applications")
        op.rename_table("workers", "applications")

    _rename_all(forward=True)


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "applications" in tables and "workers" not in tables:
        op.rename_table("applications", "workers")
    _rename_all(forward=False)
