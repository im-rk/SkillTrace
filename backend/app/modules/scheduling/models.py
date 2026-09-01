import enum
from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, Integer, Numeric, SmallInteger, CheckConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.db.base import Base

class ExamStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    live = "live"
    closed = "closed"

class Exam(Base):
    __tablename__ = "exams"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    
    status = Column(Enum(ExamStatus, name="exam_status", create_type=True), nullable=False, server_default='draft')
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="check_duration_minutes_positive"),
        CheckConstraint("end_time > start_time", name="end_after_start"),
        Index("idx_exams_window", "start_time", "end_time", postgresql_where=text("status IN ('scheduled', 'live')")),
    )

class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), primary_key=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), primary_key=True)
    
    question_version = Column(Integer, nullable=False)
    display_order = Column(SmallInteger, nullable=False)
    points = Column(Numeric(5, 2), nullable=False, server_default="1.0")