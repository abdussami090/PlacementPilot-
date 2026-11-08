from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class CompanyRecruitmentDrive(Base):
    __tablename__ = "company_recruitment_drives"

    id = Column(Integer, primary_key=True, index=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.id"),
        nullable=False
    )

    placement_cycle_id = Column(
        Integer,
        ForeignKey("placement_cycles.id"),
        nullable=False
    )

    name = Column(
        String,
        nullable=False
    )

    description = Column(
        Text,
        nullable=True
    )

    application_start_date = Column(
        Date,
        nullable=True
    )

    application_deadline = Column(
        Date,
        nullable=True
    )

    status = Column(
        String,
        default="Draft",
        nullable=False
    )

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    company = relationship(
        "Company"
    )

    placement_cycle = relationship(
        "PlacementCycle",
        back_populates="recruitment_drives"
    )

    jobs = relationship(
        "Job",
        back_populates="recruitment_drive"
    )