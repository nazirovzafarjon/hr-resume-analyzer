"""add email_verifications (hashed 6-digit codes) for HR accounts

Stores emailed 6-digit verification codes as bcrypt hashes:

* ``email_verifications.user_id`` — the HR account (FK users.id, ON DELETE CASCADE).
* ``code_hash`` — bcrypt digest; the raw code is never stored.
* ``expires_at`` / ``attempts`` / ``created_at`` / ``used_at``.

Also drops ``users.email_verification_issued_at``: HR verification no longer
uses link tokens (the Candidate Portal keeps its own column and link flow).

Revision ID: e6b1c4d8f2a9
Revises: d4a7b9c2e6f1
Create Date: 2026-10-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6b1c4d8f2a9"
down_revision: Union[str, None] = "d4a7b9c2e6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("email_verifications"):
        op.create_table(
            "email_verifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("code_hash", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_email_verifications_user_id", "email_verifications", ["user_id"]
        )
        op.create_index(
            "ix_email_verifications_created_at", "email_verifications", ["created_at"]
        )

    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "email_verification_issued_at" in user_columns:
        op.drop_column("users", "email_verification_issued_at")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "email_verification_issued_at" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "email_verification_issued_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )
    if inspector.has_table("email_verifications"):
        op.drop_index("ix_email_verifications_created_at", table_name="email_verifications")
        op.drop_index("ix_email_verifications_user_id", table_name="email_verifications")
        op.drop_table("email_verifications")
