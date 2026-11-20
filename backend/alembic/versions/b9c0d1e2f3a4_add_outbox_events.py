"""add outbox_events table for transactional outbox pattern

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-11-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "outbox_events" not in tables:
        op.create_table(
            "outbox_events",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column(
                "status",
                sa.Enum("pending", "published", "failed", name="outbox_status"),
                server_default="pending",
                nullable=False,
            ),
            sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            op.f("ix_outbox_events_created_at"),
            "outbox_events",
            ["created_at"],
            unique=False,
        )
        op.create_index(
            op.f("ix_outbox_events_event_type"),
            "outbox_events",
            ["event_type"],
            unique=False,
        )
        op.create_index(
            op.f("ix_outbox_events_status"),
            "outbox_events",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "outbox_events" in tables:
        op.drop_table("outbox_events")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS outbox_status")
