"""
Idempotent demo/E2E seed data: an instructor, a student, and a skill with a
real question pool across all three difficulty tiers.

    uv run python -m scripts.seed_demo

Public registration only ever creates students, so an instructor account can
only be created out of band -- this is that band.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.db.session import async_session_maker  # noqa: E402
from app.modules.iam.models import User, UserRole  # noqa: E402
from app.modules.iam.service import get_password_hash  # noqa: E402
from app.modules.question_bank.models import DifficultyLevel, Question, QuestionType  # noqa: E402
from app.modules.quiz_engine.models import Skill  # noqa: E402

DEMO_PASSWORD = "Passw0rd!demo"
INSTRUCTOR_EMAIL = "instructor@skilltrace.dev"
STUDENT_EMAIL = "student@skilltrace.dev"
SKILL_SLUG = "fractions"


def _mcq(prompt: str, choices: list[str], correct: int, difficulty: DifficultyLevel) -> dict:
    ids = "abcd"
    return {
        "question_type": QuestionType.multiple_choice,
        "prompt": prompt,
        "difficulty": difficulty,
        "content": {
            "choices": [{"id": ids[i], "text": text} for i, text in enumerate(choices)],
            "correct_choice_id": ids[correct],
        },
    }


def _tf(prompt: str, answer: bool, difficulty: DifficultyLevel) -> dict:
    return {
        "question_type": QuestionType.true_false,
        "prompt": prompt,
        "difficulty": difficulty,
        "content": {"correct_answer": answer},
    }


def _text(prompt: str, answer: str, difficulty: DifficultyLevel) -> dict:
    return {
        "question_type": QuestionType.text_input,
        "prompt": prompt,
        "difficulty": difficulty,
        "content": {"correct_answer": answer, "case_sensitive": False},
    }


E, M, H = DifficultyLevel.easy, DifficultyLevel.medium, DifficultyLevel.hard

QUESTIONS = [
    _mcq("What is 1/2 + 1/2?", ["1", "1/4", "2", "1/2"], 0, E),
    _mcq("Which fraction is the largest?", ["1/8", "1/4", "1/2", "1/3"], 2, E),
    _tf("1/2 is equal to 2/4.", True, E),
    _tf("3/4 is greater than 1.", False, E),
    _text("What is 1/4 written as a decimal?", "0.25", E),
    _mcq("What is the numerator of 5/8?", ["8", "5", "13", "3"], 1, E),
    _mcq("What is 2/3 + 1/6?", ["5/6", "3/9", "1/2", "3/6"], 0, M),
    _mcq("Simplify 12/16.", ["6/8", "3/4", "4/3", "2/3"], 1, M),
    _tf("2/5 + 2/5 = 4/10.", False, M),
    _text("What is 3/4 of 20?", "15", M),
    _mcq("What is 5/6 - 1/3?", ["1/2", "4/3", "2/3", "1/6"], 0, M),
    _tf("1/3 and 2/6 are equivalent fractions.", True, M),
    _mcq("What is (2/3) x (9/4)?", ["3/2", "6/7", "18/12 - 1", "11/7"], 0, H),
    _mcq("What is (3/5) / (9/10)?", ["2/3", "27/50", "3/2", "5/6"], 0, H),
    _text("What is 7/8 - 3/16, as a fraction over 16?", "11/16", H),
    _tf("The reciprocal of 3/7 is 7/3.", True, H),
    _mcq("Which is equal to 0.375?", ["3/8", "3/5", "5/8", "1/3"], 0, H),
    _text("What is 1 1/2 as an improper fraction?", "3/2", H),
]


async def seed() -> dict:
    password_hash = get_password_hash(DEMO_PASSWORD)
    async with async_session_maker() as session:
        instructor = (await session.execute(select(User).where(User.email == INSTRUCTOR_EMAIL))).scalars().first()
        if instructor is None:
            instructor = User(
                email=INSTRUCTOR_EMAIL, display_name="Demo Instructor", password_hash=password_hash, role=UserRole.instructor
            )
            session.add(instructor)
        student = (await session.execute(select(User).where(User.email == STUDENT_EMAIL))).scalars().first()
        if student is None:
            student = User(email=STUDENT_EMAIL, display_name="Demo Student", password_hash=password_hash, role=UserRole.student)
            session.add(student)
        await session.flush()

        skill = (await session.execute(select(Skill).where(Skill.slug == SKILL_SLUG))).scalars().first()
        if skill is None:
            skill = Skill(name="Fractions", slug=SKILL_SLUG, description="Adding, comparing and simplifying fractions", created_by=instructor.id)
            session.add(skill)
            await session.flush()

        existing = {p for (p,) in (await session.execute(select(Question.prompt).where(Question.skill_id == skill.id))).all()}
        added = 0
        for q in QUESTIONS:
            if q["prompt"] not in existing:
                session.add(Question(skill_id=skill.id, created_by=instructor.id, **q))
                added += 1
        await session.commit()
        return {"instructor": INSTRUCTOR_EMAIL, "student": STUDENT_EMAIL, "password": DEMO_PASSWORD, "skill_id": str(skill.id), "questions_added": added}


if __name__ == "__main__":
    print(asyncio.run(seed()))
