from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CandidateRound(Base):
    """Tracks one applicant's assignment and outcome in one placement round."""

    __tablename__ = "candidate_rounds"

    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "placement_round_id",
            name="uq_candidate_round_application_round",
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_candidate_round_score_0_100",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True,
    )
    placement_round_id = Column(
        Integer,
        ForeignKey("placement_rounds.id"),
        nullable=False,
        index=True,
    )
    attendance = Column(String(20), nullable=False, default="Pending")
    result = Column(String(20), nullable=False, default="Pending")
    score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    evaluated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    evaluated_at = Column(DateTime, nullable=True)

    application = relationship("Application")
    placement_round = relationship("PlacementRound")
