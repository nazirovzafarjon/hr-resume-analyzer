"""add the Telegram "AI analysis finished" preference

Phase 8 of the Telegram bot: HR users can switch off the message that tells
them an AI analysis they started has finished (or failed).

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-11-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("telegram_links")}
    if "notify_analysis" not in columns:
        op.add_column(
            "telegram_links",
            sa.Column("notify_analysis", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    op.drop_column("telegram_links", "notify_analysis")
