import pytest
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import alembic.config
import alembic.command

from app.modules.iam.models import User, UserRole
from app.modules.quiz_engine.models import Skill, QuizSession, Response, SessionStatus
from app.modules.question_bank.models import Question, QuestionType, DifficultyLevel
from app.modules.scheduling.models import Exam, ExamStatus
from app.modules.enrollment.models import ExamAccessCode
from app.modules.live_session_gateway.models import ExamSession, ExamSessionStatus


async def create_base_fixtures(db_session: AsyncSession):
    """Create basic user and skill required for foreign key constraints."""
    user = User(
        email=f"instructor_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Test Instructor",
        password_hash="hashed_pw",
        role=UserRole.instructor,
    )
    skill = Skill(
        name="Calculus Derivatives",
        slug=f"calculus-derivatives-{uuid.uuid4().hex[:8]}",
        p_l0=Decimal("0.3000"),
        p_t=Decimal("0.1500"),
        p_g=Decimal("0.2000"),
        p_s=Decimal("0.1000"),
        mastery_threshold=Decimal("0.8500"),
    )
    db_session.add_all([user, skill])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(skill)
    return user, skill


@pytest.mark.asyncio
async def test_case_1_valid_mcq_succeeds(db_session: AsyncSession):
    """Case 1: Insert multiple_choice question with valid content -> Succeeds."""
    user, skill = await create_base_fixtures(db_session)
    q = Question(
        skill_id=skill.id,
        question_type=QuestionType.multiple_choice,
        prompt="What is the derivative of x^2?",
        difficulty=DifficultyLevel.easy,
        content={"choices": [{"id": "a", "text": "2x"}, {"id": "b", "text": "x"}], "correct_choice_id": "a"},
        created_by=user.id,
    )
    db_session.add(q)
    await db_session.commit()
    assert q.id is not None


@pytest.mark.asyncio
async def test_case_2_invalid_mcq_missing_correct_choice_id(db_session: AsyncSession):
    """Case 2: Insert multiple_choice question missing correct_choice_id -> IntegrityError."""
    user, skill = await create_base_fixtures(db_session)
    q = Question(
        skill_id=skill.id,
        question_type=QuestionType.multiple_choice,
        prompt="What is the derivative of x^2?",
        difficulty=DifficultyLevel.easy,
        content={"choices": [{"id": "a", "text": "2x"}]},  # Missing correct_choice_id
        created_by=user.id,
    )
    db_session.add(q)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_case_3_valid_true_false_succeeds(db_session: AsyncSession):
    """Case 3: Insert true_false question with content={'correct_answer': true} -> Succeeds."""
    user, skill = await create_base_fixtures(db_session)
    q = Question(
        skill_id=skill.id,
        question_type=QuestionType.true_false,
        prompt="Derivative of a constant is 0.",
        difficulty=DifficultyLevel.easy,
        content={"correct_answer": True},
        created_by=user.id,
    )
    db_session.add(q)
    await db_session.commit()
    assert q.id is not None


@pytest.mark.asyncio
async def test_case_4_invalid_true_false_empty_content(db_session: AsyncSession):
    """Case 4: Insert true_false question with empty content={} -> IntegrityError."""
    user, skill = await create_base_fixtures(db_session)
    q = Question(
        skill_id=skill.id,
        question_type=QuestionType.true_false,
        prompt="Derivative of a constant is 0.",
        difficulty=DifficultyLevel.easy,
        content={},  # Missing correct_answer
        created_by=user.id,
    )
    db_session.add(q)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_case_5_duplicate_exam_session_rejected(db_session: AsyncSession):
    """Case 5: Insert two exam_sessions rows for the same (user_id, exam_id) -> Second insert: IntegrityError."""
    user, skill = await create_base_fixtures(db_session)
    now = datetime.now(timezone.utc)
    exam = Exam(
        title="Midterm Calculus",
        skill_id=skill.id,
        start_time=now,
        end_time=now + timedelta(hours=2),
        duration_minutes=90,
        status=ExamStatus.scheduled,
        created_by=user.id,
    )
    db_session.add(exam)
    await db_session.commit()

    # First session succeeds
    session1 = ExamSession(
        exam_id=exam.id,
        student_id=user.id,
        status=ExamSessionStatus.in_progress,
    )
    db_session.add(session1)
    await db_session.commit()

    # Second session for same exam & student fails
    session2 = ExamSession(
        exam_id=exam.id,
        student_id=user.id,
        status=ExamSessionStatus.in_progress,
    )
    db_session.add(session2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_case_6_response_both_sessions_rejected(db_session: AsyncSession):
    """Case 6: Insert a responses row with both session_id and exam_session_id set -> IntegrityError."""
    user, skill = await create_base_fixtures(db_session)
    now = datetime.now(timezone.utc)
    exam = Exam(
        title="Midterm",
        skill_id=skill.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
        duration_minutes=60,
        created_by=user.id,
    )
    q = Question(
        skill_id=skill.id,
        question_type=QuestionType.true_false,
        prompt="True or False?",
        difficulty=DifficultyLevel.easy,
        content={"correct_answer": True},
    )
    quiz_s = QuizSession(
        student_id=user.id,
        skill_id=skill.id,
        initial_mastery=Decimal("0.30000"),
    )
    db_session.add_all([exam, q, quiz_s])
    await db_session.commit()

    exam_s = ExamSession(exam_id=exam.id, student_id=user.id)
    db_session.add(exam_s)
    await db_session.commit()

    # Response with BOTH session_id and exam_session_id
    resp = Response(
        session_id=quiz_s.id,
        exam_session_id=exam_s.id,
        question_id=q.id,
        submitted_answer="True",
        is_correct=True,
        mastery_before=Decimal("0.30000"),
        mastery_after=Decimal("0.71000"),
        p_t_used=Decimal("0.1500"),
        p_g_used=Decimal("0.2000"),
        p_s_used=Decimal("0.1000"),
    )
    db_session.add(resp)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_case_7_response_neither_session_rejected(db_session: AsyncSession):
    """Case 7: Insert a responses row with neither session_id nor exam_session_id set -> IntegrityError."""
    user, skill = await create_base_fixtures(db_session)
    q = Question(
        skill_id=skill.id,
        question_type=QuestionType.true_false,
        prompt="True or False?",
        difficulty=DifficultyLevel.easy,
        content={"correct_answer": True},
    )
    db_session.add(q)
    await db_session.commit()

    # Response with NEITHER session_id nor exam_session_id
    resp = Response(
        session_id=None,
        exam_session_id=None,
        question_id=q.id,
        submitted_answer="True",
        is_correct=True,
        mastery_before=Decimal("0.30000"),
        mastery_after=Decimal("0.71000"),
        p_t_used=Decimal("0.1500"),
        p_g_used=Decimal("0.2000"),
        p_s_used=Decimal("0.1000"),
    )
    db_session.add(resp)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_case_8_exam_end_before_start_rejected(db_session: AsyncSession):
    """Case 8: Create an exam with end_time before start_time -> IntegrityError."""
    user, skill = await create_base_fixtures(db_session)
    now = datetime.now(timezone.utc)
    exam = Exam(
        title="Invalid Times Exam",
        skill_id=skill.id,
        start_time=now,
        end_time=now - timedelta(minutes=10),  # end_time is BEFORE start_time
        duration_minutes=60,
        created_by=user.id,
    )
    db_session.add(exam)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_case_9_access_code_exceeded_max_uses_rejected(db_session: AsyncSession):
    """Case 9: Insert an exam_access_codes row with times_used > max_uses -> IntegrityError."""
    user, skill = await create_base_fixtures(db_session)
    now = datetime.now(timezone.utc)
    exam = Exam(
        title="Exam with Access Code",
        skill_id=skill.id,
        start_time=now,
        end_time=now + timedelta(hours=2),
        duration_minutes=60,
        created_by=user.id,
    )
    db_session.add(exam)
    await db_session.commit()

    code = ExamAccessCode(
        code=f"CODE-{uuid.uuid4().hex[:6]}",
        exam_id=exam.id,
        max_uses=5,
        times_used=6,  # Violates check_times_used
    )
    db_session.add(code)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_case_10_migration_downgrade_and_upgrade_cycle():
    """Case 10: Full teardown (alembic downgrade base) and rebuild (alembic upgrade head) succeeds cleanly."""
    import asyncio
    cfg = alembic.config.Config("alembic.ini")
    # Downgrade all the way to base in a worker thread so asyncio.run() runs independently
    await asyncio.to_thread(alembic.command.downgrade, cfg, "base")
    # Re-apply all migrations up to head
    await asyncio.to_thread(alembic.command.upgrade, cfg, "head")
