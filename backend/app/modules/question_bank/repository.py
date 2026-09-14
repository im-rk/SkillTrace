"""
Data access repository for Question Bank.
"""
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.question_bank.models import Question, Tag


async def get_or_create_tags(session: AsyncSession, names: list[str]) -> list[Tag]:
    normalized = {n.strip().lower() for n in names if n.strip()}
    if not normalized:
        return []
    result = await session.execute(select(Tag).where(Tag.name.in_(normalized)))
    existing = {t.name: t for t in result.scalars().all()}
    new_tags = [Tag(name=name) for name in normalized - existing.keys()]
    if new_tags:
        session.add_all(new_tags)
        await session.flush()
    return [*existing.values(), *new_tags]


async def create(session: AsyncSession, question: Question, tags: list[Tag]) -> Question:
    question.tags = tags
    session.add(question)
    await session.flush()
    return question


def _base_query():
    return select(Question).where(Question.deleted_at.is_(None)).options(selectinload(Question.tags))


async def get_by_id(session: AsyncSession, question_id: UUID) -> Question | None:
    result = await session.execute(_base_query().where(Question.id == question_id))
    return result.scalars().first()


async def get_by_ids(session: AsyncSession, question_ids: list[UUID]) -> list[Question]:
    if not question_ids:
        return []
    result = await session.execute(_base_query().where(Question.id.in_(question_ids)))
    return list(result.scalars().all())


async def list_questions(
    session: AsyncSession,
    skill_id: UUID | None = None,
    difficulty: str | None = None,
    tag_names: list[str] | None = None,
) -> list[Question]:
    stmt = _base_query()
    if skill_id is not None:
        stmt = stmt.where(Question.skill_id == skill_id)
    if difficulty is not None:
        stmt = stmt.where(Question.difficulty == difficulty)
    if tag_names:
        normalized = [t.strip().lower() for t in tag_names if t.strip()]
        stmt = stmt.where(Question.tags.any(Tag.name.in_(normalized)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update(session: AsyncSession, question: Question, tags: list[Tag] | None) -> Question:
    question.version += 1
    if tags is not None:
        question.tags = tags
    await session.flush()
    return question


async def soft_delete(session: AsyncSession, question: Question) -> None:
    question.deleted_at = datetime.now(timezone.utc)
    await session.flush()
