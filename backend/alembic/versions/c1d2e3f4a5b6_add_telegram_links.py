"""add telegram_links and telegram_link_tokens tables

Binds a Telegram account to an HR user or a candidate account so the bot can
send notifications (phase 1 of the Telegram bot: account linking only).

Revision ID: c1d2e3f4a5b6
Revises: b9c0d1e2f3a4
Create Date: 2026-11-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ONE_OWNER = (
    "(kind = 'hr' AND user_id IS NOT NULL AND candidate_account_id IS NULL) OR "
    "(kind = 'candidate' AND candidate_account_id IS NOT NULL AND user_id IS NULL)"
)

_kind = postgresql.ENUM("hr", "candidate", name="telegram_account_kind", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("hr", "candidate", name="telegram_account_kind").create(
        bind, checkfirst=True
    )
    tables = set(sa.inspect(bind).get_table_names())

    if "telegram_links" not in tables:
        op.create_table(
            "telegram_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", _kind, nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
                unique=True,
            ),
            sa.Column(
                "candidate_account_id",
                sa.Integer(),
                sa.ForeignKey("candidate_accounts.id", ondelete="CASCADE"),
                nullable=True,
                unique=True,
            ),
            sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
            sa.Column("chat_id", sa.BigInteger(), nullable=False),
            sa.Column("username", sa.String(length=64), nullable=True),
            sa.Column("first_name", sa.String(length=255), nullable=True),
            sa.Column("language", sa.String(length=8), nullable=False, server_default="uz"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "linked_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(_ONE_OWNER, name="ck_telegram_links_one_owner"),
            sa.UniqueConstraint(
                "telegram_user_id", "kind", name="uq_telegram_links_telegram_user_kind"
            ),
        )
        op.create_index(
            "ix_telegram_links_telegram_user_id", "telegram_links", ["telegram_user_id"]
        )

    if "telegram_link_tokens" not in tables:
        op.create_table(
            "telegram_link_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", _kind, nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "candidate_account_id",
                sa.Integer(),
                sa.ForeignKey("candidate_accounts.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(_ONE_OWNER, name="ck_telegram_link_tokens_one_owner"),
        )
        op.create_index(
            "ix_telegram_link_tokens_user_id", "telegram_link_tokens", ["user_id"]
        )
        op.create_index(
            "ix_telegram_link_tokens_candidate_account_id",
            "telegram_link_tokens",
            ["candidate_account_id"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_link_tokens_candidate_account_id", table_name="telegram_link_tokens"
    )
    op.drop_index("ix_telegram_link_tokens_user_id", table_name="telegram_link_tokens")
    op.drop_table("telegram_link_tokens")
    op.drop_index("ix_telegram_links_telegram_user_id", table_name="telegram_links")
    op.drop_table("telegram_links")
    postgresql.ENUM(name="telegram_account_kind").drop(op.get_bind(), checkfirst=True)
