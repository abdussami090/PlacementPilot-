from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class SavedJob(Base):
    """A student's saved/bookmarked placement job."""

    __tablename__ = "saved_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_saved_job_user_job"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
    job = relationship("Job")
