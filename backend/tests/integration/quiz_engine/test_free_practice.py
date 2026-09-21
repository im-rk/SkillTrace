"""
Free-practice adaptive quiz: session lifecycle, the difficulty policy, the BKT
update on every answer, and the mastery-over-time progress feed.
"""
import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.db.session import get_db
from app.main import app as fastapi_app
from app.modules.evaluation_pipeline.queue_producer import submit_answer as enqueue_exam_answer
from app.modules.evaluation_pipeline.tasks import _process_submission
from app.modules.quiz_engine.domain.bkt.engine import update_mastery
from app.modules.quiz_engine.domain.bkt.params import DEFAULT_PARAMS
from app.modules.quiz_engine.models import StudentSkillState

CORRECT = "b"
WRONG = "a"


async def add_question(client, headers, skill_id, difficulty="easy", prompt=None) -> str:
    res = await client.post(
        "/question-bank/questions",
        json={
            "skill_id": skill_id,
            "question_type": "multiple_choice",
            "prompt": prompt or f"{difficulty} {uuid.uuid4().hex[:6]}",
            "difficulty": difficulty,
            "content": {"choices": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}], "correct_choice_id": CORRECT},
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest.fixture
async def practice(client, instructor, student, skill_id):
    """A skill with 3 questions per tier and a student ready to practise it."""
    instructor_headers, _ = instructor
    student_headers, student_id = student
    for tier in ("easy", "medium", "hard"):
        for _ in range(3):
            await add_question(client, instructor_headers, skill_id, tier)
    return {
        "skill_id": skill_id,
        "student_headers": student_headers,
        "student_id": student_id,
        "instructor_headers": instructor_headers,
    }


async def start(client, p) -> dict:
    res = await client.post("/quiz-sessions", json={"skill_id": p["skill_id"]}, headers=p["student_headers"])
    assert res.status_code == 201, res.text
    return res.json()


async def next_q(client, p, session_id):
    return await client.get(f"/quiz-sessions/{session_id}/next-question", headers=p["student_headers"])


async def answer(client, p, session_id, question_id, submitted):
    return await client.post(
        f"/quiz-sessions/{session_id}/answer",
        json={"question_id": question_id, "submitted_answer": submitted},
        headers=p["student_headers"],
    )


@pytest.fixture
async def concurrent_client(client, db_session):
    """Like `client`, but each request gets its own DB session -- the shared one would
    interleave concurrent requests inside a single transaction. Depends on `client` so
    it is set up after it and its get_db override wins."""
    maker = async_sessionmaker(bind=db_session.bind, expire_on_commit=False, autoflush=False)

    async def per_request_session():
        async with maker() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = per_request_session
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# --- starting a session -------------------------------------------------------

@pytest.mark.asyncio
async def test_start_session_initialises_mastery_to_p_l0(client, practice):
    session = await start(client, practice)
    assert session["status"] == "in_progress"
    assert session["initial_mastery"] == pytest.approx(0.3)
    assert session["current_mastery"] == pytest.approx(0.3)
    assert session["questions_answered"] == 0


@pytest.mark.asyncio
async def test_start_resumes_the_in_progress_session(client, practice):
    first = await start(client, practice)
    second = await start(client, practice)
    assert first["id"] == second["id"]


@pytest.mark.asyncio
async def test_concurrent_starts_create_one_session(concurrent_client, practice):
    results = await asyncio.gather(*[start(concurrent_client, practice) for _ in range(5)])
    assert len({r["id"] for r in results}) == 1


@pytest.mark.asyncio
async def test_start_needs_questions_and_a_live_skill(client, instructor, student, skill_id):
    student_headers, _ = student
    empty = await client.post("/quiz-sessions", json={"skill_id": skill_id}, headers=student_headers)
    assert empty.status_code == 409

    missing = await client.post("/quiz-sessions", json={"skill_id": str(uuid.uuid4())}, headers=student_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_session_starts_from_existing_mastery_not_p_l0(client, db_session, practice):
    # e.g. the student already answered exam questions on this skill
    db_session.add(StudentSkillState(student_id=uuid.UUID(practice["student_id"]), skill_id=uuid.UUID(practice["skill_id"]), current_mastery=0.6))
    await db_session.commit()

    session = await start(client, practice)
    assert session["initial_mastery"] == pytest.approx(0.6)
    question = (await next_q(client, practice, session["id"])).json()["question"]
    assert question["difficulty"] == "medium"  # 0.4 <= 0.6 < 0.85


# --- next question / policy ---------------------------------------------------

@pytest.mark.asyncio
async def test_low_mastery_gets_an_easy_question_without_the_answer(client, practice):
    session = await start(client, practice)
    body = (await next_q(client, practice, session["id"])).json()

    assert body["status"] == "in_progress"
    assert body["question"]["difficulty"] == "easy"  # 0.3 < 0.4
    assert "correct_choice_id" not in str(body)
    assert set(body["question"]["content"]) == {"choices"}


@pytest.mark.asyncio
async def test_next_question_skips_answered_and_falls_back_to_other_tiers(client, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, student_id = student
    p = {"skill_id": skill_id, "student_headers": student_headers, "student_id": student_id}
    only_medium = await add_question(client, instructor_headers, skill_id, "medium")
    session = await start(client, p)

    first = (await next_q(client, p, session["id"])).json()
    assert first["question"]["id"] == only_medium  # no easy question exists -> nearest tier
    await answer(client, p, session["id"], only_medium, WRONG)

    # the only question is now answered -> pool exhausted, session ends
    second = (await next_q(client, p, session["id"])).json()
    assert second["status"] == "exhausted" and second["question"] is None
    assert (await client.get(f"/quiz-sessions/{session['id']}", headers=student_headers)).json()["status"] == "abandoned"


@pytest.mark.asyncio
async def test_already_mastered_student_is_told_so_and_session_ends(client, db_session, practice):
    db_session.add(StudentSkillState(student_id=uuid.UUID(practice["student_id"]), skill_id=uuid.UUID(practice["skill_id"]), current_mastery=0.9))
    await db_session.commit()
    session = await start(client, practice)

    body = (await next_q(client, practice, session["id"])).json()
    assert body["status"] == "mastered" and body["question"] is None
    ended = (await client.get(f"/quiz-sessions/{session['id']}", headers=practice["student_headers"])).json()
    assert ended["status"] == "mastered" and ended["final_mastery"] == pytest.approx(0.9)


# --- answering ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_every_answer_is_the_exact_bkt_update_and_reaching_the_threshold_ends_the_session(client, practice):
    session = await start(client, practice)
    expected = 0.3
    final_status = "in_progress"
    for _ in range(9):
        body = (await next_q(client, practice, session["id"])).json()
        if body["status"] != "in_progress":
            break
        res = await answer(client, practice, session["id"], body["question"]["id"], CORRECT)
        assert res.status_code == 200, res.text
        result = res.json()
        assert result["is_correct"] is True
        assert result["mastery_before"] == pytest.approx(expected, abs=1e-4)
        expected = update_mastery(expected, True, DEFAULT_PARAMS)
        assert result["mastery_after"] == pytest.approx(expected, abs=1e-4)
        final_status = result["session_status"]
        if final_status == "mastered":
            break

    assert final_status == "mastered"
    assert expected >= 0.85
    done = (await client.get(f"/quiz-sessions/{session['id']}", headers=practice["student_headers"])).json()
    assert done["status"] == "mastered"
    assert done["final_mastery"] == pytest.approx(expected, abs=1e-4)
    assert done["ended_at"] is not None
    # a finished session accepts nothing further
    assert (await next_q(client, practice, session["id"])).status_code == 409


@pytest.mark.asyncio
async def test_a_wrong_answer_lowers_mastery(client, practice):
    session = await start(client, practice)
    question = (await next_q(client, practice, session["id"])).json()["question"]
    result = (await answer(client, practice, session["id"], question["id"], WRONG)).json()

    assert result["is_correct"] is False
    assert result["mastery_after"] == pytest.approx(update_mastery(0.3, False, DEFAULT_PARAMS), abs=1e-4)
    assert result["mastery_after"] < 0.3 + 0.15  # sanity: slip/guess math, not a free win
    assert result["session_status"] == "in_progress"


@pytest.mark.asyncio
async def test_a_question_can_only_be_answered_once_per_session(client, practice):
    session = await start(client, practice)
    question = (await next_q(client, practice, session["id"])).json()["question"]
    assert (await answer(client, practice, session["id"], question["id"], WRONG)).status_code == 200
    assert (await answer(client, practice, session["id"], question["id"], CORRECT)).status_code == 409


@pytest.mark.asyncio
async def test_concurrent_double_submit_is_graded_once(concurrent_client, db_session, practice):
    session = await start(concurrent_client, practice)
    question = (await next_q(concurrent_client, practice, session["id"])).json()["question"]

    responses = await asyncio.gather(*[answer(concurrent_client, practice, session["id"], question["id"], CORRECT) for _ in range(4)])

    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409]
    state = (await concurrent_client.get(f"/quiz-sessions/{session['id']}", headers=practice["student_headers"])).json()
    assert state["questions_answered"] == 1
    assert state["current_mastery"] == pytest.approx(update_mastery(0.3, True, DEFAULT_PARAMS), abs=1e-4)


@pytest.mark.asyncio
async def test_answering_a_question_of_another_skill_is_404(client, instructor, practice, make_user, db_session):
    other_skill = (await client.post("/skills", json={"name": "Other", "slug": f"other-{uuid.uuid4().hex[:8]}"}, headers=practice["instructor_headers"])).json()["id"]
    foreign = await add_question(client, practice["instructor_headers"], other_skill)
    session = await start(client, practice)
    assert (await answer(client, practice, session["id"], foreign, CORRECT)).status_code == 404


@pytest.mark.asyncio
async def test_bkt_params_are_read_from_the_skill_at_answer_time(client, practice):
    patch = await client.patch(
        f"/skills/{practice['skill_id']}", json={"p_t": 0.5, "p_g": 0.1, "p_s": 0.05}, headers=practice["instructor_headers"]
    )
    assert patch.status_code == 200
    session = await start(client, practice)
    question = (await next_q(client, practice, session["id"])).json()["question"]
    result = (await answer(client, practice, session["id"], question["id"], CORRECT)).json()

    from app.modules.quiz_engine.domain.bkt.params import BKTParams
    assert result["mastery_after"] == pytest.approx(update_mastery(0.3, True, BKTParams(0.3, 0.5, 0.1, 0.05)), abs=1e-4)


# --- quitting / ownership -----------------------------------------------------

@pytest.mark.asyncio
async def test_quit_ends_the_session_and_is_idempotent(client, practice):
    session = await start(client, practice)
    question = (await next_q(client, practice, session["id"])).json()["question"]
    await answer(client, practice, session["id"], question["id"], WRONG)

    first = await client.post(f"/quiz-sessions/{session['id']}/quit", headers=practice["student_headers"])
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "abandoned" and body["ended_at"] is not None
    assert body["final_mastery"] == pytest.approx(body["current_mastery"])

    assert (await client.post(f"/quiz-sessions/{session['id']}/quit", headers=practice["student_headers"])).json() == body
    assert (await answer(client, practice, session["id"], question["id"], CORRECT)).status_code == 409
    # and a fresh session can be started afterwards, from the mastery reached so far
    assert (await start(client, practice))["id"] != session["id"]


@pytest.mark.asyncio
async def test_another_student_cannot_touch_the_session(client, practice, make_user):
    from app.modules.iam.models import UserRole
    other_headers, _ = await make_user(UserRole.student)
    session = await start(client, practice)
    question = (await next_q(client, practice, session["id"])).json()["question"]

    assert (await client.get(f"/quiz-sessions/{session['id']}", headers=other_headers)).status_code == 404
    assert (await client.get(f"/quiz-sessions/{session['id']}/next-question", headers=other_headers)).status_code == 404
    forged = await client.post(
        f"/quiz-sessions/{session['id']}/answer", json={"question_id": question["id"], "submitted_answer": CORRECT}, headers=other_headers
    )
    assert forged.status_code == 404
    assert (await client.post(f"/quiz-sessions/{session['id']}/quit", headers=other_headers)).status_code == 404
    assert (await client.post("/quiz-sessions", json={"skill_id": practice["skill_id"]})).status_code == 401


# --- progress -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_progress_is_a_continuous_chain_across_exam_and_practice(client, db_session, redis_client, started_exam, skill_id):
    student_headers, student_id = started_exam["student_headers"], started_exam["student_id"]
    # exam answer first (graded through the real pipeline task), then practice answers
    log = await enqueue_exam_answer(
        db_session, redis_client, uuid.UUID(started_exam["session_id"]), uuid.UUID(started_exam["question_ids"][0]), CORRECT, uuid.UUID(student_id)
    )
    await _process_submission(str(log.id))

    p = {"skill_id": skill_id, "student_headers": student_headers, "student_id": student_id}
    for _ in range(3):
        await add_question(client, started_exam["instructor_headers"], skill_id, "medium")
    session = await start(client, p)
    assert session["initial_mastery"] == pytest.approx(update_mastery(0.3, True, DEFAULT_PARAMS), abs=1e-4)  # continues the exam's chain
    for correct in (False, True):  # a correct one first would already cross 0.85 and end the session
        question = (await next_q(client, p, session["id"])).json()["question"]
        await answer(client, p, session["id"], question["id"], CORRECT if correct else WRONG)

    res = await client.get(f"/students/{student_id}/progress", params={"skill_id": skill_id}, headers=student_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [pt["source"] for pt in body["points"]] == ["exam", "practice", "practice"]
    assert [pt["is_correct"] for pt in body["points"]] == [True, False, True]
    for prev, cur in zip(body["points"], body["points"][1:]):
        assert cur["mastery_before"] == pytest.approx(prev["mastery_after"], abs=1e-4)
    assert body["current_mastery"] == pytest.approx(body["points"][-1]["mastery_after"], abs=1e-4)
    assert body["initial_mastery"] == pytest.approx(0.3)
    assert body["mastery_threshold"] == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_progress_access_control(client, practice, make_user):
    from app.modules.iam.models import UserRole
    other_headers, other_id = await make_user(UserRole.student)
    params = {"skill_id": practice["skill_id"]}

    own = await client.get(f"/students/{practice['student_id']}/progress", params=params, headers=practice["student_headers"])
    assert own.status_code == 200 and own.json()["points"] == [] and own.json()["current_mastery"] is None
    assert (await client.get(f"/students/{practice['student_id']}/progress", params=params, headers=other_headers)).status_code == 403
    assert (await client.get(f"/students/{practice['student_id']}/progress", params=params, headers=practice["instructor_headers"])).status_code == 200
    assert (await client.get(f"/students/{practice['student_id']}/mastery", headers=other_headers)).status_code == 403


@pytest.mark.asyncio
async def test_student_mastery_lists_every_skill_with_my_standing(client, practice):
    session = await start(client, practice)
    question = (await next_q(client, practice, session["id"])).json()["question"]
    await answer(client, practice, session["id"], question["id"], CORRECT)

    rows = (await client.get(f"/students/{practice['student_id']}/mastery", headers=practice["student_headers"])).json()
    mine = next(r for r in rows if r["skill_id"] == practice["skill_id"])
    assert mine["question_count"] == 9
    assert mine["total_attempts"] == 1
    assert mine["current_mastery"] == pytest.approx(update_mastery(0.3, True, DEFAULT_PARAMS), abs=1e-4)


# --- skill administration -----------------------------------------------------

@pytest.mark.asyncio
async def test_skill_patch_is_partial_validated_and_instructor_only(client, practice):
    url = f"/skills/{practice['skill_id']}"
    ok = await client.patch(url, json={"name": "Renamed", "mastery_threshold": 0.9}, headers=practice["instructor_headers"])
    assert ok.status_code == 200
    assert ok.json()["name"] == "Renamed" and ok.json()["mastery_threshold"] == pytest.approx(0.9)
    assert ok.json()["p_t"] == pytest.approx(0.15)  # untouched

    assert (await client.patch(url, json={"p_g": 1.5}, headers=practice["instructor_headers"])).status_code == 422
    assert (await client.patch(url, json={"name": "x"}, headers=practice["student_headers"])).status_code == 403
    assert (await client.patch(f"/skills/{uuid.uuid4()}", json={"name": "x"}, headers=practice["instructor_headers"])).status_code == 404


@pytest.mark.asyncio
async def test_deleted_skill_disappears_but_history_and_questions_survive(client, practice):
    session = await start(client, practice)
    question = (await next_q(client, practice, session["id"])).json()["question"]
    await answer(client, practice, session["id"], question["id"], CORRECT)

    assert (await client.delete(f"/skills/{practice['skill_id']}", headers=practice["student_headers"])).status_code == 403
    assert (await client.delete(f"/skills/{practice['skill_id']}", headers=practice["instructor_headers"])).status_code == 204

    listed = (await client.get("/skills", headers=practice["instructor_headers"])).json()
    assert practice["skill_id"] not in [s["id"] for s in listed]
    assert (await client.post("/quiz-sessions", json={"skill_id": practice["skill_id"]}, headers=practice["student_headers"])).status_code == 404
    assert (await client.delete(f"/skills/{practice['skill_id']}", headers=practice["instructor_headers"])).status_code == 404
    # the old progress is still readable
    progress = await client.get(f"/students/{practice['student_id']}/progress", params={"skill_id": practice["skill_id"]}, headers=practice["student_headers"])
    assert progress.status_code == 200 and len(progress.json()["points"]) == 1


@pytest.mark.asyncio
async def test_readiness_flags_tiers_with_no_questions(client, instructor, skill_id):
    headers, _ = instructor
    await add_question(client, headers, skill_id, "easy")
    await add_question(client, headers, skill_id, "easy")

    body = (await client.get(f"/skills/{skill_id}/readiness", headers=headers)).json()
    assert body["counts"] == {"easy": 2, "medium": 0, "hard": 0}
    assert body["ready"] is False and body["missing_tiers"] == ["medium", "hard"]

    await add_question(client, headers, skill_id, "medium")
    await add_question(client, headers, skill_id, "hard")
    assert (await client.get(f"/skills/{skill_id}/readiness", headers=headers)).json()["ready"] is True


@pytest.mark.asyncio
async def test_skill_overview_lists_students_by_mastery(client, practice, make_user):
    from app.modules.iam.models import UserRole
    session = await start(client, practice)
    question = (await next_q(client, practice, session["id"])).json()["question"]
    await answer(client, practice, session["id"], question["id"], CORRECT)

    rows = (await client.get(f"/skills/{practice['skill_id']}/overview", headers=practice["instructor_headers"])).json()
    assert [r["student_id"] for r in rows] == [practice["student_id"]]
    assert rows[0]["total_attempts"] == 1 and rows[0]["is_mastered"] is False

    assert (await client.get(f"/skills/{practice['skill_id']}/overview", headers=practice["student_headers"])).status_code == 403
