"""add application pipeline fields to workers

Extends the ``workers`` table (one row per application/candidate) with the
AI-assisted hiring pipeline fields:

* ``application_status`` — HR-reviewed application status
  (new/reviewing/shortlisted/interview/rejected/withdrawn).
* ``analysis_status`` — AI processing state
  (pending/analyzing/completed/failed), independent of the HR status.
* ``analysis_error`` — safe, user-facing reason for a failed analysis run.
* ``analysis_started_at`` — start of the current run (detects interrupted runs).
* ``candidate_at`` — set when HR moves an application into the hiring pipeline;
  ``NULL`` means "application only", so an application can never produce more
  than one candidate (the row *is* the candidate).

Safe for existing data: both new NOT NULL columns ship with server defaults,
so current rows are backfilled transparently (application_status='new',
analysis_status='pending'); the remaining columns are nullable.

Revision ID: d6a2f4c81b57
Revises: b4f1d8c2a7e3
Create Date: 2026-09-15 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d6a2f4c81b57"
down_revision: Union[str, None] = "b4f1d8c2a7e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    application_status = sa.Enum(
        "new",
        "reviewing",
        "shortlisted",
        "interview",
        "rejected",
        "withdrawn",
        name="application_status",
    )
    analysis_status = sa.Enum(
        "pending",
        "analyzing",
        "completed",
        "failed",
        name="application_analysis_status",
    )
    application_status.create(op.get_bind(), checkfirst=True)
    analysis_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "workers",
        sa.Column(
            "application_status",
            application_status,
            server_default="new",
            nullable=False,
        ),
    )
    op.add_column(
        "workers",
        sa.Column(
            "analysis_status",
            analysis_status,
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "workers",
        sa.Column("analysis_error", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "workers",
        sa.Column(
            "analysis_started_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "workers",
        sa.Column("candidate_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workers", "candidate_at")
    op.drop_column("workers", "analysis_started_at")
    op.drop_column("workers", "analysis_error")
    op.drop_column("workers", "analysis_status")
    op.drop_column("workers", "application_status")
    sa.Enum(name="application_analysis_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="application_status").drop(op.get_bind(), checkfirst=True)