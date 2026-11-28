"""add the Help Center support chat tables

HR users and candidates open support conversations from the floating Help
button; admins answer them from the Support inbox and close them when done.

Safe for existing data: two brand-new tables, nothing is altered or dropped.
Idempotent like the other migrations: a table that already exists (a database
stamped back to an older revision) is left as it is.

Revision ID: b5c8d1e4f7a2
Revises: e3f4a5b6c7d8
Create Date: 2026-11-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5c8d1e4f7a2"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "support_conversations" not in tables:
        op.create_table(
            "support_conversations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("requester_kind", sa.String(length=16), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("candidate_account_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
            sa.Column("page_url", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("admin_last_read_message_id", sa.Integer(), server_default="0", nullable=False),
            sa.Column("requester_last_read_message_id", sa.Integer(), server_default="0", nullable=False),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_by_id", sa.Integer(), nullable=True),
            sa.CheckConstraint(
                "(requester_kind = 'hr' AND user_id IS NOT NULL AND candidate_account_id IS NULL) OR "
                "(requester_kind = 'candidate' AND candidate_account_id IS NOT NULL AND user_id IS NULL)",
                name="ck_support_conversations_one_requester",
            ),
            sa.CheckConstraint("requester_kind IN ('hr', 'candidate')", name="ck_support_conversations_kind"),
            sa.CheckConstraint("status IN ('open', 'closed')", name="ck_support_conversations_status"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["candidate_account_id"], ["candidate_accounts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["closed_by_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_support_conversations_user_id", "support_conversations", ["user_id"])
        op.create_index(
            "ix_support_conversations_candidate_account_id", "support_conversations", ["candidate_account_id"]
        )
        op.create_index(
            "ix_support_conversations_status_last", "support_conversations", ["status", "last_message_at"]
        )

    if "support_messages" not in tables:
        op.create_table(
            "support_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("sender", sa.String(length=16), nullable=False),
            sa.Column("author_user_id", sa.Integer(), nullable=True),
            sa.Column("author_name", sa.String(length=255), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("sender IN ('requester', 'admin')", name="ck_support_messages_sender"),
            sa.ForeignKeyConstraint(["conversation_id"], ["support_conversations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_support_messages_conversation_id", "support_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_support_messages_conversation_id", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_conversations_status_last", table_name="support_conversations")
    op.drop_index("ix_support_conversations_candidate_account_id", table_name="support_conversations")
    op.drop_index("ix_support_conversations_user_id", table_name="support_conversations")
    op.drop_table("support_conversations")
