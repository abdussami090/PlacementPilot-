from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, DateTime
from datetime import datetime

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, unique=True, index=True, nullable=False)

    description = Column(Text, nullable=True)

    website = Column(String, nullable=True)

    contact_person = Column(String, nullable=True)

    contact_email = Column(String, nullable=True)

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )