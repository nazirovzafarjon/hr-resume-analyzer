"""admin panel: user timestamps, audit log, system errors, AI runs, settings

* ``users.created_at`` / ``users.last_login_at`` — registration and last
  sign-in time for the admin user list and growth charts. Existing accounts
  get the migration time as ``created_at`` because their real registration
  date was never recorded.
* ``audit_logs`` — append-only trail of meaningful and administrative actions.
* ``system_errors`` — 5xx responses (no bodies, no tracebacks).
* ``ai_analysis_runs`` — one row per AI provider attempt for AI monitoring.
* ``platform_settings`` — the single row of runtime admin switches.

Idempotent like the previous revisions (the app also runs ``create_all()`` on
startup, which creates the new tables but cannot add columns to ``users``).
Additive only: no existing data is changed or removed.

Revision ID: c3e8f1a9d6b4
Revises: a7c1e9d3b5f2
Create Date: 2026-09-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e8f1a9d6b4"
down_revision: Union[str, None] = "a7c1e9d3b5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    user_columns = _columns("users")
    if "created_at" not in user_columns:
        op.add_column("users", _created_at())
        op.create_index(op.f("ix_users_created_at"), "users", ["created_at"])
    if "last_login_at" not in user_columns:
        op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    tables = _tables()

    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            _created_at(),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("actor_email", sa.String(length=255), nullable=True),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("resource_type", sa.String(length=32), nullable=False),
            sa.Column("resource_id", sa.String(length=64), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"])
        op.create_index(op.f("ix_audit_logs_actor_user_id"), "audit_logs", ["actor_user_id"])
        op.create_index("ix_audit_logs_action_created_at", "audit_logs", ["action", "created_at"])
        op.create_index(
            "ix_audit_logs_resource_created_at", "audit_logs", ["resource_type", "created_at"]
        )

    if "system_errors" not in tables:
        op.create_table(
            "system_errors",
            sa.Column("id", sa.Integer(), nullable=False),
            _created_at(),
            sa.Column("request_id", sa.String(length=64), nullable=True),
            sa.Column("method", sa.String(length=10), nullable=False),
            sa.Column("path", sa.String(length=500), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("error_type", sa.String(length=120), nullable=False),
            sa.Column("message", sa.String(length=500), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_system_errors_created_at"), "system_errors", ["created_at"])
        op.create_index(op.f("ix_system_errors_request_id"), "system_errors", ["request_id"])
        op.create_index(op.f("ix_system_errors_status_code"), "system_errors", ["status_code"])

    if "ai_analysis_runs" not in tables:
        op.create_table(
            "ai_analysis_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            _created_at(),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.Column("job_id", sa.Integer(), nullable=True),
            sa.Column("worker_id", sa.Integer(), nullable=True),
            sa.Column("provider", sa.String(length=32), nullable=True),
            sa.Column("model", sa.String(length=200), nullable=True),
            sa.Column("source", sa.String(length=16), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("error_category", sa.String(length=32), nullable=True),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.String(length=500), nullable=True),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["worker_id"], ["workers.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_ai_analysis_runs_created_at"), "ai_analysis_runs", ["created_at"])
        op.create_index(op.f("ix_ai_analysis_runs_owner_id"), "ai_analysis_runs", ["owner_id"])
        op.create_index(
            "ix_ai_analysis_runs_status_created_at", "ai_analysis_runs", ["status", "created_at"]
        )

    if "platform_settings" not in tables:
        op.create_table(
            "platform_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("registration_enabled", sa.Boolean(), server_default="true", nullable=False),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column("updated_by_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    tables = _tables()
    for table in ("platform_settings", "ai_analysis_runs", "system_errors", "audit_logs"):
        if table in tables:
            op.drop_table(table)

    user_columns = _columns("users")
    if "last_login_at" in user_columns:
        op.drop_column("users", "last_login_at")
    if "created_at" in user_columns:
        op.drop_index(op.f("ix_users_created_at"), table_name="users")
        op.drop_column("users", "created_at")
