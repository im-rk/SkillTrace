import enum
from sqlalchemy import Column, String, Text, DateTime, Numeric, Enum, ForeignKey, Boolean, Integer, CheckConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.db.base import Base

class SessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    mastered = "mastered"
    abandoned = "abandoned"

class Skill(Base):
    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(150), nullable=False)
    slug = Column(String(160), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    p_l0 = Column(Numeric(5, 4), nullable=False, server_default="0.3000")
    p_t = Column(Numeric(5, 4), nullable=False, server_default="0.1500")
    p_g = Column(Numeric(5, 4), nullable=False, server_default="0.2000")
    p_s = Column(Numeric(5, 4), nullable=False, server_default="0.1000")
    mastery_threshold = Column(Numeric(5, 4), nullable=False, server_default="0.8500")
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("p_l0 >= 0 AND p_l0 <= 1", name="check_p_l0"),
        CheckConstraint("p_t >= 0 AND p_t <= 1", name="check_p_t"),
        CheckConstraint("p_g >= 0 AND p_g <= 1", name="check_p_g"),
        CheckConstraint("p_s >= 0 AND p_s <= 1", name="check_p_s"),
        CheckConstraint("mastery_threshold >= 0 AND mastery_threshold <= 1", name="check_mastery_threshold"),
        Index("idx_skills_active", "id", postgresql_where=text("deleted_at IS NULL")),
    )

class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    status = Column(Enum(SessionStatus, name="session_status", create_type=True), nullable=False, server_default='in_progress')
    initial_mastery = Column(Numeric(6, 5), nullable=False)
    final_mastery = Column(Numeric(6, 5), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_sessions_student", "student_id", "started_at"),
        Index("idx_sessions_active", "student_id", "skill_id", postgresql_where=text("status = 'in_progress'")),
    )

class Response(Base):
    __tablename__ = "responses"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    session_id = Column(UUID(as_uuid=True), ForeignKey("quiz_sessions.id"), nullable=True)
    exam_session_id = Column(UUID(as_uuid=True), ForeignKey("exam_sessions.id"), nullable=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    
    submitted_answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    
    mastery_before = Column(Numeric(6, 5), nullable=False)
    mastery_after = Column(Numeric(6, 5), nullable=False)
    
    p_t_used = Column(Numeric(5, 4), nullable=False)
    p_g_used = Column(Numeric(5, 4), nullable=False)
    p_s_used = Column(Numeric(5, 4), nullable=False)
    
    answered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    points_awarded = Column(Numeric(5, 2), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(session_id IS NOT NULL AND exam_session_id IS NULL) OR (session_id IS NULL AND exam_session_id IS NOT NULL)",
            name="exactly_one_session_type"
        ),
        CheckConstraint("mastery_before >= 0 AND mastery_before <= 1", name="check_mastery_before"),
        CheckConstraint("mastery_after >= 0 AND mastery_after <= 1", name="check_mastery_after"),
        Index("idx_responses_session", "session_id", "answered_at"),
        Index("idx_responses_question", "question_id"),
    )

class StudentSkillState(Base):
    __tablename__ = "student_skill_state"

    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"), primary_key=True)
    current_mastery = Column(Numeric(6, 5), nullable=False)
    total_attempts = Column(Integer, nullable=False, server_default="0")
    is_mastered = Column(Boolean, nullable=False, server_default="false")
    last_updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    diff = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
    )