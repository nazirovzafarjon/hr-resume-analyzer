"""add google oauth to candidate accounts

* ``candidate_accounts.google_id`` — Google "sub" claim identifier (unique, indexed, nullable).
* ``candidate_accounts.picture`` — Google avatar profile picture URL (nullable).
* ``candidate_accounts.hashed_password`` — Made nullable to support Google-only candidate accounts.

Revision ID: c1f9e8a2b3d4
Revises: b8e2f6a4c1d7
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1f9e8a2b3d4"
down_revision: Union[str, None] = "b8e2f6a4c1d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    columns = {c["name"] for c in inspector.get_columns("candidate_accounts")}

    if "google_id" not in columns:
        op.add_column(
            "candidate_accounts",
            sa.Column("google_id", sa.String(length=255), nullable=True),
        )
        op.create_index(
            "ix_candidate_accounts_google_id",
            "candidate_accounts",
            ["google_id"],
            unique=True,
        )

    if "picture" not in columns:
        op.add_column(
            "candidate_accounts",
            sa.Column("picture", sa.String(length=1024), nullable=True),
        )

    # Alter hashed_password to be nullable for Google-only candidate accounts
    op.alter_column(
        "candidate_accounts",
        "hashed_password",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    inspector = _inspector()
    columns = {c["name"] for c in inspector.get_columns("candidate_accounts")}

    op.alter_column(
        "candidate_accounts",
        "hashed_password",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    if "picture" in columns:
        op.drop_column("candidate_accounts", "picture")

    if "google_id" in columns:
        op.drop_index("ix_candidate_accounts_google_id", table_name="candidate_accounts")
        op.drop_column("candidate_accounts", "google_id")
