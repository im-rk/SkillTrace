"""
Business logic service for Question Bank.
"""
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.question_bank import repository
from app.modules.question_bank.models import Question
from app.modules.question_bank.schemas import (
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
)
from app.modules.quiz_engine.models import AuditLog


def _to_response(question: Question) -> QuestionResponse:
    return QuestionResponse(
        id=question.id,
        skill_id=question.skill_id,
        question_type=question.question_type,
        prompt=question.prompt,
        difficulty=question.difficulty,
        content=question.content,
        version=question.version,
        tags=[t.name for t in question.tags],
    )


def _audit_entry(actor_id: UUID | None, action: str, question_id: UUID, diff: dict | None = None) -> AuditLog:
    return AuditLog(actor_id=actor_id, action=action, entity_type="question", entity_id=question_id, diff=diff)


async def create_question(session: AsyncSession, data: QuestionCreate, actor_id: UUID | None) -> QuestionResponse:
    question = Question(
        skill_id=data.skill_id,
        question_type=data.question_type,
        prompt=data.prompt,
        difficulty=data.difficulty,
        content=data.content.model_dump(),
        created_by=actor_id,
    )
    tags = await repository.get_or_create_tags(session, data.tags)
    question = await repository.create(session, question, tags)
    session.add(_audit_entry(actor_id, "create", question.id, diff=data.model_dump(mode="json")))
    await session.commit()
    return _to_response(question)


async def get_question(session: AsyncSession, question_id: UUID) -> QuestionResponse:
    question = await repository.get_by_id(session, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return _to_response(question)


async def list_questions(
    session: AsyncSession,
    skill_id: UUID | None = None,
    difficulty: str | None = None,
    tags: list[str] | None = None,
) -> list[QuestionResponse]:
    if skill_id is None and not tags:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="skill_id or tags is required")
    questions = await repository.list_questions(session, skill_id, difficulty, tags)
    return [_to_response(q) for q in questions]


async def update_question(
    session: AsyncSession, question_id: UUID, data: QuestionUpdate, actor_id: UUID | None
) -> QuestionResponse:
    question = await repository.get_by_id(session, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    updates = data.model_dump(exclude_unset=True, exclude={"tags"})
    if "content" in updates and updates["content"] is not None:
        updates["content"] = data.content.model_dump()
    for field, value in updates.items():
        setattr(question, field, value)

    tags = await repository.get_or_create_tags(session, data.tags) if data.tags is not None else None
    question = await repository.update(session, question, tags)
    session.add(_audit_entry(actor_id, "update", question.id, diff=data.model_dump(mode="json", exclude_unset=True)))
    await session.commit()
    return _to_response(question)


async def delete_question(session: AsyncSession, question_id: UUID, actor_id: UUID | None) -> None:
    question = await repository.get_by_id(session, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    await repository.soft_delete(session, question)
    session.add(_audit_entry(actor_id, "delete", question.id))
    await session.commit()
