"""
Business logic for IAM module.
Includes auth, JWT generation, and password hashing.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.core.config import settings
from app.modules.iam.schemas import UserCreate, UserLogin, Token, TokenData
from app.modules.iam.repository import get_user_by_email, create_user
from app.modules.iam.models import User, UserRole


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    """Stateless JWT decode shared by REST's get_current_user (raises on failure)
    and the WebSocket access guard (catches and returns None on failure)."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    user_id = payload.get("sub")
    role = payload.get("role")
    if user_id is None or role is None:
        raise jwt.InvalidTokenError("Token missing sub or role claim")
    return TokenData(user_id=user_id, role=UserRole(role))


async def register_user(
    session: AsyncSession,
    user_in: UserCreate,
    enforce_student_role: bool = True,
) -> User:
    user = await get_user_by_email(session, user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    # Safeguard against role elevation via public registration
    effective_role = UserRole.student if enforce_student_role else user_in.role
    user_data = user_in.model_copy(update={"role": effective_role})
    # bcrypt is deliberately slow (~100-300ms) and synchronous -- calling it
    # directly here would block the single-threaded event loop for the
    # duration, serializing every other concurrent request behind it. Found
    # via Phase 12's load test: 50 concurrent logins produced multi-second
    # p95 latency and, under chaos-test load, an outright client timeout.
    # asyncio.to_thread runs it on a worker thread instead.
    hashed_password = await asyncio.to_thread(get_password_hash, user_in.password)
    new_user = await create_user(session, user_data, hashed_password)
    return new_user


async def authenticate_user(session: AsyncSession, login_data: UserLogin) -> Token:
    user = await get_user_by_email(session, login_data.email)
    if user is None or not await asyncio.to_thread(verify_password, login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in_seconds,
    )