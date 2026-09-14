"""
Service for CSV/JSON parsing, per-row validation, and partial-success reporting.
"""
import csv
import io
import json
from uuid import UUID
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.question_bank.schemas import (
    QuestionCreate,
    BulkImportRowResult,
    BulkImportResponse,
)
from app.modules.question_bank import service


def _row_to_schema(row: dict, skill_id: UUID) -> QuestionCreate:
    content = row.get("content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"content is not valid JSON: {e}")

    tags = row.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return QuestionCreate(
        skill_id=skill_id,
        question_type=row.get("question_type"),
        prompt=row.get("prompt"),
        difficulty=row.get("difficulty"),
        content=content,
        tags=tags,
    )


def parse_csv(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [{k.strip(): v for k, v in row.items()} for row in reader]


async def bulk_import(
    session: AsyncSession, skill_id: UUID, rows: list[dict], actor_id: UUID | None
) -> BulkImportResponse:
    results: list[BulkImportRowResult] = []
    for i, row in enumerate(rows, start=1):
        try:
            question_create = _row_to_schema(row, skill_id)
            question = await service.create_question(session, question_create, actor_id)
            results.append(
                BulkImportRowResult(row_number=i, status="success", question_id=question.id)
            )
        except (ValidationError, ValueError) as e:
            results.append(BulkImportRowResult(row_number=i, status="failed", error=str(e)))
            continue
        except DBAPIError as e:
            await session.rollback()
            results.append(BulkImportRowResult(row_number=i, status="failed", error=str(e.orig)))
            continue

    return BulkImportResponse(
        total_rows=len(rows),
        succeeded=sum(1 for r in results if r.status == "success"),
        failed=sum(1 for r in results if r.status == "failed"),
        results=results,
    )
