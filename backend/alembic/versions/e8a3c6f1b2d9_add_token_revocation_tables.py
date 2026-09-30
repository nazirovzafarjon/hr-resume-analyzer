"""persist token revocations: revoked_tokens and session_cutoffs

Token revocation (refresh-token rotation, logout, workspace switching,
"sign out everywhere" after a password change) used to live in the API
process's memory, so a restart or a second worker forgot it. These tables make
it durable and shared. Additive and idempotent like the previous revisions;
starts empty (previously revoked tokens were lost on every restart anyway).

Revision ID: e8a3c6f1b2d9
Revises: d5b7e2c4f8a1
Create Date: 2026-09-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8a3c6f1b2d9"
down_revision: Union[str, None] = "d5b7e2c4f8a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "revoked_tokens" not in tables:
        op.create_table(
            "revoked_tokens",
            sa.Column("jti", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "revoked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
            ),
            sa.PrimaryKeyConstraint("jti"),
        )
        op.create_index(op.f("ix_revoked_tokens_expires_at"), "revoked_tokens", ["expires_at"])
    if "session_cutoffs" not in tables:
        op.create_table(
            "session_cutoffs",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("cutoff", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )


def downgrade() -> None:
    tables = _tables()
    if "session_cutoffs" in tables:
        op.drop_table("session_cutoffs")
    if "revoked_tokens" in tables:
        op.drop_index(op.f("ix_revoked_tokens_expires_at"), table_name="revoked_tokens")
        op.drop_table("revoked_tokens")
