"""add analysis_batch_items table for Celery batch processing

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-11-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "analysis_batch_items" not in tables:
        op.create_table(
            "analysis_batch_items",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("batch_id", sa.Integer(), nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=False),
            sa.Column("celery_task_id", sa.String(length=255), nullable=True),
            sa.Column(
                "status",
                sa.Enum(
                    "pending",
                    "running",
                    "completed",
                    "failed",
                    "skipped",
                    "cancelled",
                    name="batch_item_status",
                ),
                server_default="pending",
                nullable=False,
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["application_id"],
                ["applications.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["batch_id"],
                ["analysis_batches.id"],
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("batch_id", "application_id", name="uq_batch_item_batch_application"),
        )
        op.create_index(
            op.f("ix_analysis_batch_items_application_id"),
            "analysis_batch_items",
            ["application_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_analysis_batch_items_batch_id"),
            "analysis_batch_items",
            ["batch_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_analysis_batch_items_celery_task_id"),
            "analysis_batch_items",
            ["celery_task_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_analysis_batch_items_status"),
            "analysis_batch_items",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "analysis_batch_items" in tables:
        op.drop_table("analysis_batch_items")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS batch_item_status")
