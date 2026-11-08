from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class PlacementCycle(Base):
    __tablename__ = "placement_cycles"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(
        String,
        nullable=False
    )

    academic_year = Column(
        String,
        nullable=False
    )

    description = Column(
        Text,
        nullable=True
    )

    start_date = Column(
        Date,
        nullable=True
    )

    end_date = Column(
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

    recruitment_drives = relationship(
        "CompanyRecruitmentDrive",
        back_populates="placement_cycle"
    )

    policy = relationship(
    "PlacementPolicy",
    back_populates="placement_cycle",
    uselist=False,
    cascade="all, delete-orphan"
)