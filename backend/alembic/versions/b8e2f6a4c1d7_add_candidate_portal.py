"""add candidate portal: candidate accounts, status history, 'hired' status

* ``candidate_accounts`` — job seeker accounts for the Candidate Portal
  (separate from the HR ``users`` table, see ``app.models.candidate_account``).
* ``applications.candidate_account_id`` — the account that submitted the
  application while signed in (NULL for guests and HR-entered applications).
* ``application_status_history`` — one row per status an application entered,
  so the candidate timeline shows real dates. Existing applications get no
  rows: their real status dates were never recorded and are not invented.
* ``application_status`` enum gains ``hired`` (final positive decision).

Idempotent like the previous revisions, so a database created from the models
by ``create_all`` can be stamped and upgraded safely.

Revision ID: b8e2f6a4c1d7
Revises: 2cb0c8660dbf
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e2f6a4c1d7"
down_revision: Union[str, None] = "2cb0c8660dbf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    # Runs inside the migration transaction (allowed since PostgreSQL 12 as
    # long as the new value is not used in the same transaction, and it is not
    # here). No autocommit block: the API's startup migration runs on a
    # connection that is already inside a transaction.
    op.execute("ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'hired' AFTER 'interview'")

    inspector = _inspector()
    tables = set(inspector.get_table_names())

    if "candidate_accounts" not in tables:
        op.create_table(
            "candidate_accounts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("profile_image", sa.String(length=1024), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_candidate_accounts_email", "candidate_accounts", ["email"], unique=True
        )

    columns = {c["name"] for c in inspector.get_columns("applications")}
    if "candidate_account_id" not in columns:
        op.add_column(
            "applications", sa.Column("candidate_account_id", sa.Integer(), nullable=True)
        )
        op.create_foreign_key(
            "applications_candidate_account_id_fkey",
            "applications",
            "candidate_accounts",
            ["candidate_account_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_applications_candidate_account_id", "applications", ["candidate_account_id"]
        )

    if "application_status_history" not in tables:
        op.create_table(
            "application_status_history",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_application_status_history_application_id",
            "application_status_history",
            ["application_id"],
        )


def downgrade() -> None:
    inspector = _inspector()
    tables = set(inspector.get_table_names())
    if "application_status_history" in tables:
        op.drop_table("application_status_history")
    columns = {c["name"] for c in inspector.get_columns("applications")}
    if "candidate_account_id" in columns:
        op.drop_index("ix_applications_candidate_account_id", table_name="applications")
        op.drop_constraint(
            "applications_candidate_account_id_fkey", "applications", type_="foreignkey"
        )
        op.drop_column("applications", "candidate_account_id")
    if "candidate_accounts" in tables:
        op.drop_table("candidate_accounts")
    # 'hired' stays in the enum: PostgreSQL cannot drop a single enum value,
    # and rows may already use it.
