from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey
)
from sqlalchemy.orm import relationship

from app.database import Base


class Education(Base):
    __tablename__ = "educations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    degree = Column(String)
    college = Column(String)
    year = Column(String)
    cgpa = Column(String)

    # New placement eligibility fields
    graduation_year = Column(
        Integer,
        nullable=True
    )

    active_backlogs = Column(
        Integer,
        default=0,
        nullable=False
    )

    user = relationship(
        "User",
        back_populates="educations"
    )