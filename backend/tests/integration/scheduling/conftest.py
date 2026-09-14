import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quiz_engine.models import Skill


@pytest.fixture
async def skill_id(db_session: AsyncSession) -> str:
    skill = Skill(name=f"Skill {uuid.uuid4().hex[:6]}", slug=f"skill-{uuid.uuid4().hex[:8]}")
    db_session.add(skill)
    await db_session.commit()
    await db_session.refresh(skill)
    return str(skill.id)


async def create_exam(
    client: AsyncClient,
    instructor_headers: dict,
    skill_id: str,
    start_offset: timedelta = timedelta(minutes=-5),
    end_offset: timedelta = timedelta(minutes=55),
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Midterm",
        "skill_id": skill_id,
        "start_time": (now + start_offset).isoformat(),
        "end_time": (now + end_offset).isoformat(),
        "duration_minutes": 60,
    }
    res = await client.post("/exams", json=payload, headers=instructor_headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]
