"""add ai analysis fields to workers

Adds the AI screening tracking columns to the existing ``workers`` table:
``ai_score`` (0-100 suitability score), ``ai_analysis_details`` (JSON payload
with matched/missing skills, per-skill breakdown and summary) and
``submitted_at`` (application submission timestamp for the Applications UI).

Safe for existing data: both new NOT NULL columns ship with server defaults,
so current rows are backfilled transparently (ai_score=0, submitted_at=now()).

Revision ID: 13b19d3707e5
Revises: 48ff307e839f
Create Date: 2026-09-09 22:40:38.912095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13b19d3707e5'
down_revision: Union[str, None] = '48ff307e839f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'workers',
        sa.Column('ai_score', sa.Float(), server_default='0', nullable=False),
    )
    op.add_column(
        'workers',
        sa.Column('ai_analysis_details', sa.JSON(), nullable=True),
    )
    op.add_column(
        'workers',
        sa.Column(
            'submitted_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('workers', 'submitted_at')
    op.drop_column('workers', 'ai_analysis_details')
    op.drop_column('workers', 'ai_score')