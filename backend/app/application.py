from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    job_id = Column(
        Integer,
        ForeignKey("jobs.id")
    )

    status = Column(
        String,
        default="Applied"
    )

    user = relationship(
        "User",
        back_populates="applications"
    )

    job = relationship(
        "Job",
        back_populates="applications"
    )