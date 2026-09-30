"""add contact_messages table

Stores submissions from the landing page's public Contact Us form: the
visitor's first/last name, the email the team replies to, and the message.

Safe for existing data: this is a brand-new table, nothing is altered or
dropped.

Revision ID: f4a8b2c6d1e9
Revises: e3c9a1f7b2d4
Create Date: 2026-09-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4a8b2c6d1e9"
down_revision: Union[str, None] = "e3c9a1f7b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contact_messages_id"), "contact_messages", ["id"], unique=False)
    op.create_index(op.f("ix_contact_messages_email"), "contact_messages", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_contact_messages_email"), table_name="contact_messages")
    op.drop_index(op.f("ix_contact_messages_id"), table_name="contact_messages")
    op.drop_table("contact_messages")
