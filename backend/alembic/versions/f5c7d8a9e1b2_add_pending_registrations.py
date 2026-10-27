"""add pending_registrations table for two-phase HR registration

Stores pending unverified HR accounts prior to email confirmation.
No row is inserted into users until the email verification token/code is consumed.

Revision ID: f5c7d8a9e1b2
Revises: e6b1c4d8f2a9
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5c7d8a9e1b2"
down_revision: Union[str, None] = "e6b1c4d8f2a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("pending_registrations"):
        op.create_table(
            "pending_registrations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("code_hash", sa.String(length=255), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "last_sent_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
        )
        op.create_index(
            "ix_pending_registrations_email",
            "pending_registrations",
            ["email"],
            unique=True,
        )
        op.create_index(
            "ix_pending_registrations_token_hash",
            "pending_registrations",
            ["token_hash"],
            unique=False,
        )
        op.create_index(
            "ix_pending_registrations_expires_at",
            "pending_registrations",
            ["expires_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_pending_registrations_expires_at", table_name="pending_registrations"
    )
    op.drop_index(
        "ix_pending_registrations_token_hash", table_name="pending_registrations"
    )
    op.drop_index(
        "ix_pending_registrations_email", table_name="pending_registrations"
    )
    op.drop_table("pending_registrations")
