from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.db.base import Base

class ExamEnrollment(Base):
    __tablename__ = "exam_enrollments"

    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), primary_key=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    enrolled_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class ExamAccessCode(Base):
    __tablename__ = "exam_access_codes"

    code = Column(String(50), primary_key=True)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    
    max_uses = Column(Integer, nullable=True)
    times_used = Column(Integer, nullable=False, server_default="0")
    
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("max_uses IS NULL OR times_used <= max_uses", name="check_times_used"),
    )