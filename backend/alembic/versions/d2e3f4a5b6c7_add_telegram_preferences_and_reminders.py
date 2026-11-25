"""add Telegram notification preferences and interview reminders

Phase 5 of the Telegram bot: per-link switches changed from ``/settings`` and
a table that remembers which interview reminders were already sent.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-11-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PREFERENCES = ("notify_status", "notify_new_applications", "notify_reminders")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("telegram_links")}
    for name in _PREFERENCES:
        if name not in columns:
            op.add_column(
                "telegram_links",
                sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true()),
            )

    if "telegram_interview_reminders" not in set(inspector.get_table_names()):
        op.create_table(
            "telegram_interview_reminders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "interview_id",
                sa.Integer(),
                sa.ForeignKey("interviews.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("reminder_window", sa.String(length=8), nullable=False),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "interview_id",
                "reminder_window",
                "scheduled_at",
                name="uq_telegram_interview_reminders",
            ),
            sa.CheckConstraint(
                "reminder_window IN ('24h', '1h')",
                name="ck_telegram_interview_reminders_window",
            ),
        )
        op.create_index(
            "ix_telegram_interview_reminders_interview_id",
            "telegram_interview_reminders",
            ["interview_id"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_interview_reminders_interview_id",
        table_name="telegram_interview_reminders",
    )
    op.drop_table("telegram_interview_reminders")
    for name in reversed(_PREFERENCES):
        op.drop_column("telegram_links", name)
