import enum
from sqlalchemy import Column, String, Text, DateTime, Enum, Index, text
from sqlalchemy.dialects.postgresql import UUID, CITEXT
from sqlalchemy.sql import func
from app.core.db.base import Base

class UserRole(str, enum.Enum):
    student = "student"
    instructor = "instructor"
    admin = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(CITEXT, unique=True, nullable=False)
    display_name = Column(String(120), nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Enum(UserRole, name="user_role", create_type=True), nullable=False, server_default='student')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_users_role", "role", postgresql_where=text("deleted_at IS NULL")),
    )