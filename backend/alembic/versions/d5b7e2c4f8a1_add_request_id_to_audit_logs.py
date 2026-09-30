"""add request_id to audit_logs

Lets an audit entry be matched with the server log and the System Errors page
(e.g. to follow a ROLE_SELECTED / ROLE_SWITCHED event). Additive and
idempotent like the previous revisions.

Revision ID: d5b7e2c4f8a1
Revises: c3e8f1a9d6b4
Create Date: 2026-09-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5b7e2c4f8a1"
down_revision: Union[str, None] = "c3e8f1a9d6b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "request_id" not in _columns("audit_logs"):
        op.add_column("audit_logs", sa.Column("request_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    if "request_id" in _columns("audit_logs"):
        op.drop_column("audit_logs", "request_id")
