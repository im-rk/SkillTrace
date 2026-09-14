import enum
from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, Integer, CheckConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db.base import Base

class DifficultyLevel(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"

class QuestionType(str, enum.Enum):
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    text_input = "text_input"

class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    question_type = Column(Enum(QuestionType, name="question_type", create_type=True), nullable=False)
    prompt = Column(Text, nullable=False)
    difficulty = Column(Enum(DifficultyLevel, name="difficulty_level", create_type=True), nullable=False)
    
    # Polymorphic content
    content = Column(JSONB, nullable=False)
    
    version = Column(Integer, nullable=False, server_default="1")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(question_type = 'multiple_choice' AND content ? 'choices' AND content ? 'correct_choice_id') OR "
            "(question_type = 'true_false' AND content ? 'correct_answer') OR "
            "(question_type = 'text_input' AND content ? 'correct_answer')",
            name="content_matches_type"
        ),
        Index("idx_questions_skill_difficulty", "skill_id", "difficulty", postgresql_where=text("deleted_at IS NULL")),
        Index("idx_questions_content_gin", "content", postgresql_using="gin"),
    )

    tags = relationship("Tag", secondary="question_tags")

class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(60), unique=True, nullable=False)

class QuestionTag(Base):
    __tablename__ = "question_tags"

    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), primary_key=True)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("tags.id"), primary_key=True)