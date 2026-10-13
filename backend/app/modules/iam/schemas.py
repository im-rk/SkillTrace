"""
Pydantic schemas for IAM request/response payloads.
"""
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.modules.iam.models import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    display_name: str
    role: UserRole = UserRole.student


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    """Who is signed in: enough to greet them and show an avatar."""
    user_id: UUID
    role: UserRole
    display_name: str
    email: EmailStr


class TokenData(BaseModel):
    user_id: UUID
    role: UserRole

    @property
    def id(self) -> UUID:
        return self.user_id