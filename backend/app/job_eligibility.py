from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    ForeignKey,
    DateTime,
    JSON
)

from app.database import Base


class JobEligibility(Base):
    __tablename__ = "job_eligibilities"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        unique=True,
        nullable=False,
        index=True
    )

    eligible_courses = Column(
        JSON,
        default=list,
        nullable=False
    )

    eligible_branches = Column(
        JSON,
        default=list,
        nullable=False
    )

    graduation_years = Column(
        JSON,
        default=list,
        nullable=False
    )

    min_cgpa = Column(
        Float,
        nullable=True
    )

    max_active_backlogs = Column(
        Integer,
        nullable=True
    )

    notes = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )