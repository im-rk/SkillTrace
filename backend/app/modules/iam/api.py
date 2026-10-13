"""
REST API routes for IAM.
Includes /auth/register, /auth/login.
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.db.session import get_db
from app.modules.iam import repository
from app.modules.iam.schemas import UserCreate, UserLogin, Token, UserResponse, TokenData, MeResponse
from app.modules.iam.service import register_user, authenticate_user
from app.api.v1.rate_limits import auth_rate_limit
from app.modules.iam.deps import get_current_user, require_instructor, require_admin

router = APIRouter(prefix="/auth", tags=["iam"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth_rate_limit)])
async def register(user_in: UserCreate, session: AsyncSession = Depends(get_db)):
    """
    Register a new user. Public registration defaults to student role.
    """
    user = await register_user(session, user_in)
    return user

@router.post("/login", response_model=Token, dependencies=[Depends(auth_rate_limit)])
async def login(login_data: UserLogin, response: Response, session: AsyncSession = Depends(get_db)):
    """
    Authenticate user, set an httpOnly auth cookie for the browser frontend,
    and also return the token in the body for non-browser/API clients.
    """
    token = await authenticate_user(session, login_data)
    response.set_cookie(
        key=settings.ACCESS_TOKEN_COOKIE_NAME,
        value=token.access_token,
        max_age=token.expires_in,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return token

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(key=settings.ACCESS_TOKEN_COOKIE_NAME, path="/")

@router.get("/me", response_model=MeResponse)
async def me(current_user: TokenData = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """
    Who is signed in. The token proves identity and role; the name and email are read from the user row.
    """
    user = await repository.get_user_by_id(session, current_user.user_id)
    if user is None:  # a valid token for a user that no longer exists
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
    return MeResponse(user_id=user.id, role=user.role, display_name=user.display_name, email=user.email)

@router.get("/instructor-only", response_model=TokenData)
async def instructor_only_endpoint(current_user: TokenData = Depends(require_instructor)):
    """
    Protected endpoint accessible by instructors and admins.
    """
    return current_user

@router.get("/admin-only", response_model=TokenData)
async def admin_only_endpoint(current_user: TokenData = Depends(require_admin)):
    """
    Protected endpoint accessible strictly by admins.
    """
    return current_user