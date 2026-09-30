"""add user_ai_provider_configs; track skipped items on analysis_batches

* ``user_ai_provider_configs`` — one row per HR user with their own AI
  provider, model and encrypted API key (Settings -> "Connect your provider
  and API key").
* ``analysis_batches`` (Auto Analyze) was only ever created by
  ``create_all()``; it is created here when missing, and gains
  ``skipped_count``.

Idempotent: the app creates missing tables with ``create_all()`` on startup,
so each step first checks what already exists. No data is changed.

Revision ID: a7c1e9d3b5f2
Revises: f4a8b2c6d1e9
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7c1e9d3b5f2"
down_revision: Union[str, None] = "f4a8b2c6d1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tables = _tables()

    if "analysis_batches" not in tables:
        batch_status = postgresql.ENUM(
            "queued", "running", "completed", "cancelled", "failed",
            name="analysis_batch_status",
            create_type=False,
        )
        batch_status.create(op.get_bind(), checkfirst=True)
        op.create_table(
            "analysis_batches",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("worker_ids", sa.JSON(), nullable=False),
            sa.Column("current_index", sa.Integer(), server_default="0", nullable=False),
            sa.Column("successful_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("current_worker_id", sa.Integer(), nullable=True),
            sa.Column("status", batch_status, server_default="queued", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_analysis_batches_owner_id"), "analysis_batches", ["owner_id"])
    elif "skipped_count" not in _columns("analysis_batches"):
        op.add_column(
            "analysis_batches",
            sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        )

    if "user_ai_provider_configs" not in tables:
        op.create_table(
            "user_ai_provider_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("api_key_encrypted", sa.Text(), nullable=False),
            sa.Column("api_key_last4", sa.String(length=4), nullable=False),
            sa.Column("model_id", sa.String(length=200), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_user_ai_provider_configs_user_id"),
            "user_ai_provider_configs",
            ["user_id"],
            unique=True,
        )


def downgrade() -> None:
    if "user_ai_provider_configs" in _tables():
        op.drop_index(op.f("ix_user_ai_provider_configs_user_id"), table_name="user_ai_provider_configs")
        op.drop_table("user_ai_provider_configs")
    # analysis_batches predates this revision on most databases (create_all),
    # so only the column added here is removed.
    if "analysis_batches" in _tables() and "skipped_count" in _columns("analysis_batches"):
        op.drop_column("analysis_batches", "skipped_count")
