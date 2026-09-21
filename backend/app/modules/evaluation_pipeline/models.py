import enum
from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, Numeric, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.db.base import Base

class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class SubmissionQueueLog(Base):
    __tablename__ = "submission_queue_log"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    session_id = Column(UUID(as_uuid=True), ForeignKey("exam_sessions.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    
    submitted_answer = Column(Text, nullable=False)
    
    p_t_used = Column(Numeric(5, 4), nullable=False)
    p_g_used = Column(Numeric(5, 4), nullable=False)
    p_s_used = Column(Numeric(5, 4), nullable=False)
    points_possible = Column(Numeric(5, 2), nullable=False)
    
    status = Column(Enum(SubmissionStatus, name="submission_status", create_type=True), nullable=False, server_default='pending')
    
    enqueued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_submission_log_status", "status", postgresql_where=text("status = 'failed'")),
        # One answer per question per session. Without it a double-click or client retry
        # would be graded twice: double score and a double BKT observation.
        Index(
            "uq_submission_session_question",
            "session_id",
            "question_id",
            unique=True,
            postgresql_where=text("status <> 'failed'"),
        ),
    )
