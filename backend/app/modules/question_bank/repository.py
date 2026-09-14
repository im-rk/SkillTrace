"""
Data access repository for Question Bank.
"""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone

from app.modules.question_bank.models import Question, Tag, QuestionTag


async def get_or_create_tags(session: AsyncSession, names: list[str]) -> list[Tag]:
    normalized = {n.strip().lower() for n in names if n.strip()}
    if not normalized:
        return []
    result = await session.execute(select(Tag).where(Tag.name.in_(normalized)))
    existing = {t.name: t for t in result.scalars().all()}
    tags = []
    for name in normalized:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name)
            session.add(tag)
            await session.flush()
        tags.append(tag)
    return tags


async def create(session: AsyncSession, question: Question, tags: list[Tag]) -> Question:
    session.add(question)
    await session.flush()
    for tag in tags:
        session.add(QuestionTag(question_id=question.id, tag_id=tag.id))
    await session.commit()
    return await get_by_id(session, question.id)


async def get_by_id(session: AsyncSession, question_id: UUID) -> Question | None:
    result = await session.execute(
        select(Question)
        .where(Question.id == question_id, Question.deleted_at.is_(None))
        .options(selectinload(Question.tags))
    )
    return result.scalars().first()


async def list_by_skill_and_difficulty(
    session: AsyncSession, skill_id: UUID, difficulty: str | None = None
) -> list[Question]:
    stmt = select(Question).where(Question.skill_id == skill_id, Question.deleted_at.is_(None))
    if difficulty is not None:
        stmt = stmt.where(Question.difficulty == difficulty)
    stmt = stmt.options(selectinload(Question.tags))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_by_tags(session: AsyncSession, tag_names: list[str]) -> list[Question]:
    normalized = [t.strip().lower() for t in tag_names if t.strip()]
    if not normalized:
        return []
    stmt = (
        select(Question)
        .join(QuestionTag, QuestionTag.question_id == Question.id)
        .join(Tag, Tag.id == QuestionTag.tag_id)
        .where(Tag.name.in_(normalized), Question.deleted_at.is_(None))
        .options(selectinload(Question.tags))
        .distinct()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update(session: AsyncSession, question: Question, tags: list[Tag] | None) -> Question:
    question.version += 1
    if tags is not None:
        await session.execute(
            QuestionTag.__table__.delete().where(QuestionTag.question_id == question.id)
        )
        for tag in tags:
            session.add(QuestionTag(question_id=question.id, tag_id=tag.id))
    await session.commit()
    return await get_by_id(session, question.id)


async def soft_delete(session: AsyncSession, question: Question) -> None:
    question.deleted_at = datetime.now(timezone.utc)
    await session.commit()
