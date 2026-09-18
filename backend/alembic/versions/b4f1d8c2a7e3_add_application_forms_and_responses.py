"""add application forms and responses tables

Introduces the public application form feature:

* ``application_forms`` — one configuration per job: the reviewed field
  definitions (JSON list) and the high-entropy ``public_token`` used in the
  shareable application link (``/apply/<token>``). ``job_id`` is a unique FK
  with ON DELETE CASCADE so jobs keep their existing delete behaviour.
* ``application_responses`` — the structured answers snapshot of a public
  submission, one row per candidate (worker), ON DELETE CASCADE.

No existing table is altered, so existing jobs/candidates/users are
untouched. The MVP bootstrap (``Base.metadata.create_all``) also creates
both tables on fresh databases.

Revision ID: b4f1d8c2a7e3
Revises: c7d3e5f2a1b9
Create Date: 2026-09-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4f1d8c2a7e3"
down_revision: Union[str, None] = "c7d3e5f2a1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_forms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("public_token", sa.String(length=64), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_application_forms_job_id", "application_forms", ["job_id"]
    )
    op.create_index(
        "ix_application_forms_public_token", "application_forms", ["public_token"], unique=True
    )

    op.create_table(
        "application_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "worker_id",
            sa.Integer(),
            sa.ForeignKey("workers.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("responses", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_application_responses_worker_id", "application_responses", ["worker_id"]
    )


def downgrade() -> None:
    op.drop_table("application_responses")
    op.drop_index("ix_application_forms_public_token", table_name="application_forms")
    op.drop_index("ix_application_forms_job_id", table_name="application_forms")
    op.drop_table("application_forms")
