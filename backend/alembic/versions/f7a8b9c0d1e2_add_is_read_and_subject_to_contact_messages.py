"""add is_read and subject to contact_messages

Revision ID: f7a8b9c0d1e2
Revises: f6a9b3d8e1c2
Create Date: 2026-11-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "f6a9b3d8e1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("contact_messages")}
    
    if "subject" not in columns:
        op.add_column("contact_messages", sa.Column("subject", sa.String(length=255), nullable=True))
    
    if "is_read" not in columns:
        op.add_column(
            "contact_messages",
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        op.create_index(
            op.f("ix_contact_messages_is_read"),
            "contact_messages",
            ["is_read"],
            unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("contact_messages")}
    
    if "is_read" in columns:
        indexes = {idx["name"] for idx in inspector.get_indexes("contact_messages")}
        if "ix_contact_messages_is_read" in indexes:
            op.drop_index(op.f("ix_contact_messages_is_read"), table_name="contact_messages")
        op.drop_column("contact_messages", "is_read")
    
    if "subject" in columns:
        op.drop_column("contact_messages", "subject")
