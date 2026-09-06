"""
Pydantic schemas for IAM request/response payloads.
"""
from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from app.modules.iam.models import UserRole

class UserCreate(BaseModel):
    email: EmailStr
    password: str
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
    token_type: str

class TokenData(BaseModel):
    user_id: UUID
    role: UserRole