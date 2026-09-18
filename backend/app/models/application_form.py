"""SQLAlchemy models for the public application form feature.

Two new tables (no existing table is altered, so ``Base.metadata.create_all()``
bootstraps them safely and existing data is untouched):

* ``ApplicationForm`` — the structured application-form configuration of a
  job: which fields candidates must fill in, in which order, plus the public
  token used in the shareable application link. One per job.
* ``ApplicationResponse`` — the candidate's structured answers snapshot for a
  submission (one per worker/candidate). Stored next to the existing Worker
  record so the candidate pipeline keeps working unchanged.

Stored data is always *configuration/answers*, never generated UI: the public
form's layout is rendered by the frontend's fixed template.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ApplicationForm(Base):
    """Application-form configuration for a job (one per job).

    ``fields`` holds the ordered list of field definitions (label, type,
    required, options, ...) that the fixed public template renders.
    ``public_token`` is the high-entropy secret used in the shareable
    application link (``/apply/<public_token>``) — never a sequential id.
    """

    __tablename__ = "application_forms"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, index=True
    )
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped["Job"] = relationship(back_populates="application_form")


class ApplicationResponse(Base):
    """A candidate's structured answers for one application submission.

    One row per submitted application (worker). ``responses`` snapshots what
    the candidate answered (field id/key/label/type + value) so the HR
    pipeline keeps a stable record even if the form config changes later.
    """

    __tablename__ = "application_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    worker_id: Mapped[int] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), unique=True, index=True
    )
    responses: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    worker: Mapped["Worker"] = relationship(back_populates="application_response")