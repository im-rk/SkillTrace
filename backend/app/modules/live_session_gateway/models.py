import enum
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.db.base import Base

class ExamSessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    paused_disconnected = "paused_disconnected"
    submitted = "submitted"
    auto_submitted = "auto_submitted"
    expired = "expired"

class SessionEventType(str, enum.Enum):
    started = "started"
    paused = "paused"
    resumed = "resumed"
    submitted = "submitted"
    auto_submitted = "auto_submitted"
    force_closed = "force_closed"

class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    status = Column(Enum(ExamSessionStatus, name="exam_session_status", create_type=True), nullable=False, server_default='in_progress')
    
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    total_time_used_seconds = Column(Integer, nullable=False, server_default="0")
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="one_session_per_student_per_exam"),
        Index("idx_exam_sessions_status", "status", postgresql_where=text("status IN ('in_progress', 'paused_disconnected')")),
        # Covers find_stale_sessions' status='in_progress' AND last_heartbeat_at < threshold
        # lookup (Celery Beat sweep, every ~15s) with a tight index range scan
        # instead of falling back to a filter over the whole partial index above.
        Index(
            "idx_exam_sessions_stale_lookup",
            "last_heartbeat_at",
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

class SessionEvent(Base):
    __tablename__ = "session_events"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    session_id = Column(UUID(as_uuid=True), ForeignKey("exam_sessions.id"), nullable=False)
    
    event_type = Column(Enum(SessionEventType, name="session_event_type", create_type=True), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    metadata_ = Column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_session_events_time", "session_id", "occurred_at"),
    )