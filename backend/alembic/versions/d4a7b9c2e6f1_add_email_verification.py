"""add email verification to users and candidate_accounts

Adds the email-verification gate that must be satisfied before an HR or
Candidate panel can be used:

* ``is_email_verified`` (NOT NULL, default false) on ``users`` and
  ``candidate_accounts``.
* ``email_verification_issued_at`` (nullable timestamptz): when the current
  verification link was issued, used to supersede older links on resend.

Existing rows are grandfathered as verified so accounts created before this
feature keep working — the gate only applies to registrations after the
upgrade.

Revision ID: d4a7b9c2e6f1
Revises: c1f9e8a2b3d4
Create Date: 2026-10-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4a7b9c2e6f1"
down_revision: Union[str, None] = "c1f9e8a2b3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("users", "candidate_accounts")


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for table in _TABLES:
        columns = _columns(table)
        if "is_email_verified" not in columns:
            op.add_column(
                table,
                sa.Column(
                    "is_email_verified",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
            # Grandfather accounts that existed before this feature.
            op.execute(sa.text(f"UPDATE {table} SET is_email_verified = true"))
        if "email_verification_issued_at" not in columns:
            op.add_column(
                table,
                sa.Column(
                    "email_verification_issued_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                ),
            )


def downgrade() -> None:
    for table in _TABLES:
        columns = _columns(table)
        if "email_verification_issued_at" in columns:
            op.drop_column(table, "email_verification_issued_at")
        if "is_email_verified" in columns:
            op.drop_column(table, "is_email_verified")
