from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    profile = relationship(
    "Profile",
    back_populates="user",
    uselist=False
)
    jobs = relationship(
    "Job",
    back_populates="user"
)
    resumes = relationship(
    "Resume",
    back_populates="user"
)
    skills = relationship(
    "Skill",
    back_populates="user"
)
    educations = relationship(
    "Education",
    back_populates="user"
)
    applications = relationship(
    "Application",
    back_populates="user"
)
    role = Column(
    String,
    nullable=False,
    default="student",
    server_default="student",
)
    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    email = Column(String, unique=True, index=True, nullable=False)

    password = Column(String, nullable=False)