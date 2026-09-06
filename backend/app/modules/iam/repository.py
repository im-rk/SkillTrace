"""
Database operations for IAM module.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.modules.iam.models import User
from app.modules.iam.schemas import UserCreate

async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    return result.scalars().first()

async def create_user(session: AsyncSession, user_in: UserCreate, password_hash: str) -> User:
    db_user = User(
        email=user_in.email,
        display_name=user_in.display_name,
        password_hash=password_hash,
        role=user_in.role
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user