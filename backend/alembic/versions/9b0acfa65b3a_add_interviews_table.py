"""add interviews table

Adds the ``interviews`` table for the manual HR interview management feature.

The table links a candidate (``workers.id``) to the HR user who scheduled it
(``users.id``) and stores the scheduled time, duration, lifecycle status
(``upcoming``/``completed``/``cancelled``), a manually pasted meeting link and
notes. The ``status`` column uses its own ``interview_session_status`` enum type
so it never collides with the existing ``interviewstatus`` type created by
``workers.interview_status``.

Safe for existing data: this is a brand-new table, nothing is altered or
dropped. Both ``created_at`` and ``updated_at`` ship with ``now()`` server
defaults.

Revision ID: 9b0acfa65b3a
Revises: 13b19d3707e5
Create Date: 2026-09-10 15:10:37.663106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b0acfa65b3a'
down_revision: Union[str, None] = '13b19d3707e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('interviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('candidate_id', sa.Integer(), nullable=False),
    sa.Column('hr_id', sa.Integer(), nullable=False),
    sa.Column('interviewer', sa.String(length=255), nullable=False),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('UPCOMING', 'COMPLETED', 'CANCELLED', name='interview_session_status'), nullable=False),
    sa.Column('meeting_link', sa.String(length=1024), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['workers.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['hr_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interviews_candidate_id'), 'interviews', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_interviews_hr_id'), 'interviews', ['hr_id'], unique=False)
    op.create_index(op.f('ix_interviews_id'), 'interviews', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_interviews_id'), table_name='interviews')
    op.drop_index(op.f('ix_interviews_hr_id'), table_name='interviews')
    op.drop_index(op.f('ix_interviews_candidate_id'), table_name='interviews')
    op.drop_table('interviews')
    sa.Enum(name='interview_session_status').drop(op.get_bind(), checkfirst=True)