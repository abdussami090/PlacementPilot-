from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Admin / placement-cell user who created the job
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    # Company recruitment drive this job belongs to
    recruitment_drive_id = Column(
        Integer,
        ForeignKey("company_recruitment_drives.id"),
        nullable=False
    )

    role = Column(
        String,
        nullable=False
    )

    package = Column(
        String,
        nullable=True
    )

    location = Column(
        String,
        nullable=True
    )

    status = Column(
        String,
        default="Open",
        nullable=False
    )

    user = relationship(
        "User",
        back_populates="jobs"
    )

    recruitment_drive = relationship(
        "CompanyRecruitmentDrive",
        back_populates="jobs"
    )

    applications = relationship(
        "Application",
        back_populates="job"
    )