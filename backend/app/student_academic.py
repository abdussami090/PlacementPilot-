from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime
)
from sqlalchemy.orm import relationship

from app.database import Base


class StudentAcademicDetails(Base):
    __tablename__ = "student_academic_details"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True
    )

    course = Column(
        String(100),
        nullable=False
    )

    graduation_year = Column(
        Integer,
        nullable=False
    )

    cgpa = Column(
        Float,
        nullable=False
    )

    active_backlogs = Column(
        Integer,
        default=0,
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

    user = relationship("User")