from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


class PlacementRound(Base):
    """A configurable recruitment round belonging to one company drive."""

    __tablename__ = "placement_rounds"

    __table_args__ = (
        UniqueConstraint(
            "recruitment_drive_id",
            "sequence",
            name="uq_placement_round_drive_sequence",
        ),
        CheckConstraint("sequence > 0", name="ck_placement_round_sequence_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    recruitment_drive_id = Column(
        Integer,
        ForeignKey("company_recruitment_drives.id"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    sequence = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    venue = Column(String(250), nullable=True)
    meeting_link = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="Draft")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
