from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database import Base


class UploadedResume(Base):
    """Private PDF resume uploaded by one student. One current PDF per student."""

    __tablename__ = "uploaded_resumes"
    __table_args__ = (UniqueConstraint("user_id", name="uq_uploaded_resumes_user_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(80), nullable=False, unique=True, index=True)
    storage_path = Column(Text, nullable=False)
    content_type = Column(String(100), nullable=False, default="application/pdf")
    file_size = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
