from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    text
)
from sqlalchemy.orm import relationship

from app.database import Base


class PlacementPolicy(Base):
    __tablename__ = "placement_policies"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    placement_cycle_id = Column(
        Integer,
        ForeignKey("placement_cycles.id"),
        unique=True,
        nullable=False
    )

    max_active_applications = Column(
        Integer,
        default=1,
        nullable=False
    )

    allow_reapply_after_rejection = Column(
        Boolean,
        default=True,
        nullable=False
    )

    allow_reapply_after_withdrawal = Column(
        Boolean,
        default=True,
        nullable=False
    )

    # Retained for compatibility with the old database.
    # New application logic will not use this setting.
    lock_after_selection = Column(
        Boolean,
        default=True,
        nullable=False
    )

    allow_multiple_positions_same_drive = Column(
        Boolean,
        default=False,
        nullable=False
    )

    allow_withdraw_after_shortlisting = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # New policy settings
    allow_applications_after_offer_release = Column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False
    )

    lock_after_offer_acceptance = Column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False
    )

    allow_reapply_after_offer_declined = Column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False
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

    placement_cycle = relationship(
        "PlacementCycle",
        back_populates="policy"
    )