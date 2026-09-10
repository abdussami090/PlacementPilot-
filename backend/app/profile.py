from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True
    )

    college = Column(String)
    branch = Column(String)
    year = Column(String)

    linkedin = Column(String)
    github = Column(String)

    skills = Column(String)

    user = relationship(
        "User",
        back_populates="profile"
    )