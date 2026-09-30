"""add 'new' to application_analysis_status

``AnalysisStatus.NEW`` ("never analyzed") was added to the model after
d6a2f4c81b57 created the ``application_analysis_status`` enum, but the
database type was never extended. Every insert into ``workers`` defaults to
``analysis_status='new'``, so on a database migrated to d6a2f4c81b57 all new
applications failed with ``invalid input value for enum``.

Revision ID: e3c9a1f7b2d4
Revises: d6a2f4c81b57
Create Date: 2026-09-27

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e3c9a1f7b2d4"
down_revision: Union[str, None] = "d6a2f4c81b57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot be used inside the transaction that adds
    # it, so run it in autocommit mode. IF NOT EXISTS keeps it idempotent for
    # databases that were created from the models via create_all().
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE application_analysis_status ADD VALUE IF NOT EXISTS 'new' BEFORE 'pending'"
        )


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value; rows may already use it.
    pass
