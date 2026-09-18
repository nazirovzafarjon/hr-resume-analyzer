"""SQLAlchemy model for jobs (vacancies) created by HR users.

Initial structure only.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Job(Base):
    """A vacancy/job created by an HR user."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True, server_default=func.gen_random_uuid()
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    company_name: Mapped[str] = mapped_column(String(255))
    position: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    required_skills: Mapped[str] = mapped_column(Text, default="")
    required_experience: Mapped[str] = mapped_column(String(255), default="")
    leads_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="jobs")

    # One-to-one application-form configuration (created when HR publishes
    # the public application link). Optional: jobs without a generated link
    # simply have ``application_form is None``.
    application_form: Mapped["ApplicationForm | None"] = relationship(
        back_populates="job", uselist=False, passive_deletes=True
    )

    # passive_deletes: let the database ON DELETE CASCADE remove a job's
    # workers when the job is deleted. Without it the ORM tries to set the
    # child FK to NULL, which fails because workers.job_id is NOT NULL.
    workers: Mapped[list["Worker"]] = relationship(
        back_populates="job", passive_deletes=True
    )