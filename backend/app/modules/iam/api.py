"""
REST API routes for IAM.
Includes /auth/register, /auth/login.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.session import get_db
from app.modules.iam.schemas import UserCreate, UserLogin, Token, UserResponse, TokenData
from app.modules.iam.service import register_user, authenticate_user
from app.modules.iam.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["iam"])

@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate, session: AsyncSession = Depends(get_db)):
    """
    Register a new user.
    """
    user = await register_user(session, user_in)
    return user

@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, session: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return a JWT token.
    """
    return await authenticate_user(session, login_data)

@router.get("/me", response_model=TokenData)
async def me(current_user: TokenData = Depends(get_current_user)):
    """
    Return current user data from the JWT token (stateless verification).
    """
    return current_user