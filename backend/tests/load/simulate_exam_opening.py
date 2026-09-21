"""
Phase 12 -- combined load + chaos test against the REAL Docker stack.

Not a pytest test: it needs the real services running (`docker compose up -d
backend worker stream_consumer beat`), not pytest's isolated test database.
It seeds an exam directly through the app's DB session (only start / WebSocket
/ submit go over the wire, since that is what is under test), drives N students
through it concurrently, then asserts against real database state -- never only
the script's own bookkeeping.

Usage (from backend/, stack already running on :8000):
    uv run python -m tests.load.simulate_exam_opening --students 50
    uv run python -m tests.load.simulate_exam_opening --students 50 --chaos
    uv run python -m tests.load.simulate_exam_opening --students 50 --adversarial

Exits non-zero if any assertion fails.
"""
import argparse
import asyncio
import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import websockets
from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
BASE_URL = "http://127.0.0.1:8000"
WS_BASE_URL = "ws://127.0.0.1:8000"
N_QUESTIONS = 20
STUDENT_PASSWORD = "LoadTestPassword123"
HEARTBEAT_SECONDS = 5
DRAIN_TIMEOUT_SECONDS = 120

sys.path.insert(0, str(BACKEND_DIR))

from app.core.db.session import async_session_maker  # noqa: E402
from app.modules.enrollment.models import ExamEnrollment  # noqa: E402
from app.modules.evaluation_pipeline.models import SubmissionQueueLog, SubmissionStatus  # noqa: E402
from app.modules.iam.models import User, UserRole  # noqa: E402
from app.modules.iam.service import create_access_token, get_password_hash  # noqa: E402
from app.modules.live_session_gateway.models import ExamSession  # noqa: E402
from app.modules.question_bank.models import DifficultyLevel, Question, QuestionType  # noqa: E402
from app.modules.quiz_engine.models import Response as QuizResponse  # noqa: E402
from app.modules.quiz_engine.models import Skill  # noqa: E402
from app.modules.scheduling.models import Exam, ExamQuestion  # noqa: E402

QUESTION_TYPES = [QuestionType.multiple_choice, QuestionType.true_false, QuestionType.text_input]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def _question_content(qtype: QuestionType) -> dict:
    if qtype == QuestionType.multiple_choice:
        return {"choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}], "correct_choice_id": "a"}
    if qtype == QuestionType.true_false:
        return {"correct_answer": True}
    return {"correct_answer": "answer", "case_sensitive": False}


def _pick_answer(question: dict) -> str:
    qtype = question["question_type"]
    if qtype == "multiple_choice":
        return question["content"]["choices"][0]["id"]
    return "true" if qtype == "true_false" else "answer"


async def seed_load_test_data(n_students: int) -> dict:
    password_hash = get_password_hash(STUDENT_PASSWORD)  # bcrypt is slow: hash once, reuse
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        instructor = User(
            email=f"load_instr_{uuid.uuid4().hex[:8]}@example.com", display_name="Load Instructor",
            password_hash=password_hash, role=UserRole.instructor,
        )
        skill = Skill(name="Load Test Skill", slug=f"load-{uuid.uuid4().hex[:8]}")
        session.add_all([instructor, skill])
        await session.flush()

        exam = Exam(
            title="Load Test Exam", skill_id=skill.id, start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(hours=2), duration_minutes=120, created_by=instructor.id,
        )
        other_exam = Exam(
            title="Other Exam", skill_id=skill.id, start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(hours=2), duration_minutes=120, created_by=instructor.id,
        )
        questions = [
            Question(
                skill_id=skill.id, question_type=QUESTION_TYPES[i % 3], prompt=f"Load test question {i}",
                difficulty=DifficultyLevel.easy, content=_question_content(QUESTION_TYPES[i % 3]),
                created_by=instructor.id,
            )
            for i in range(N_QUESTIONS)
        ]
        students = [
            User(
                email=f"load_student_{i}_{uuid.uuid4().hex[:6]}@example.com", display_name=f"Load Student {i}",
                password_hash=password_hash, role=UserRole.student,
            )
            for i in range(n_students)
        ]
        # An extra student enrolled only in a different exam, and one enrolled nowhere,
        # for the adversarial sweep.
        wrong_exam_student = User(
            email=f"load_wrongexam_{uuid.uuid4().hex[:6]}@example.com", display_name="Wrong Exam Student",
            password_hash=password_hash, role=UserRole.student,
        )
        unenrolled_student = User(
            email=f"load_unenrolled_{uuid.uuid4().hex[:6]}@example.com", display_name="Unenrolled Student",
            password_hash=password_hash, role=UserRole.student,
        )
        session.add_all([exam, other_exam, *questions, *students, wrong_exam_student, unenrolled_student])
        await session.flush()

        session.add_all(
            [ExamQuestion(exam_id=exam.id, question_id=q.id, question_version=1, display_order=i + 1, points=Decimal("1.0"))
             for i, q in enumerate(questions)]
            + [ExamEnrollment(exam_id=exam.id, student_id=s.id) for s in students]
            + [ExamEnrollment(exam_id=other_exam.id, student_id=wrong_exam_student.id)]
        )
        await session.commit()

        return {
            "exam_id": exam.id,
            "students": [{"id": s.id, "email": s.email} for s in students],
            "wrong_exam_student_id": wrong_exam_student.id,
            "unenrolled_student_id": unenrolled_student.id,
        }


# ---------------------------------------------------------------------------
# Docker control (chaos)
# ---------------------------------------------------------------------------

def docker_compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)


async def wait_for_health(timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                if (await client.get(f"{BASE_URL}/health", timeout=2.0)).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError(f"backend at {BASE_URL} not healthy -- is `docker compose up -d backend worker stream_consumer` running?")


# ---------------------------------------------------------------------------
# Load simulation
# ---------------------------------------------------------------------------

@dataclass
class RequestResult:
    student: str
    phase: str
    status: object
    elapsed: float = 0.0


async def run_websocket(session_id: str, token: str, email: str, results: list[RequestResult]) -> None:
    uri = f"{WS_BASE_URL}/ws/exam-sessions/{session_id}?token={token}"
    try:
        async with websockets.connect(uri, open_timeout=10) as ws:
            results.append(RequestResult(email, "ws_connect", "connected"))
            while True:
                await ws.send(json.dumps({"type": "heartbeat"}))
                await asyncio.wait_for(ws.recv(), timeout=10)
                await asyncio.sleep(HEARTBEAT_SECONDS)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 -- recorded and reported, not fatal to the run
        results.append(RequestResult(email, "ws_error", repr(exc)))


async def simulate_student(student: dict, exam_id, results: list[RequestResult]) -> None:
    email = student["email"]
    ws_task = None
    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
            login = await client.post("/auth/login", json={"email": email, "password": STUDENT_PASSWORD})
            if login.status_code != 200:
                results.append(RequestResult(email, "login", login.status_code))
                return
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            t0 = time.monotonic()
            start = await client.post(f"/exams/{exam_id}/start", headers=headers)
            results.append(RequestResult(email, "start", start.status_code, time.monotonic() - t0))
            if start.status_code != 200:
                return
            session_id = start.json()["session_id"]

            ws_task = asyncio.create_task(run_websocket(session_id, token, email, results))

            questions_res = await client.get(f"/exams/{exam_id}/questions", headers=headers)
            questions = questions_res.json()["questions"] if questions_res.status_code == 200 else []
            for question in questions:
                t0 = time.monotonic()
                submit = await client.post(
                    f"/exam-sessions/{session_id}/submit-answer",
                    json={"question_id": question["question_id"], "answer": _pick_answer(question)},
                    headers=headers,
                )
                results.append(RequestResult(email, "submit", submit.status_code, time.monotonic() - t0))
    except Exception as exc:  # noqa: BLE001 -- one student's failure must not abort the whole run
        results.append(RequestResult(email, "client_error", repr(exc)))
    finally:
        if ws_task is not None:
            ws_task.cancel()
            await asyncio.gather(ws_task, return_exceptions=True)


async def run_load_simulation(students: list[dict], exam_id) -> list[RequestResult]:
    results: list[RequestResult] = []
    await asyncio.gather(*[simulate_student(s, exam_id, results) for s in students])
    return results


# ---------------------------------------------------------------------------
# Adversarial sweep -- interleaved with legitimate load
# ---------------------------------------------------------------------------

async def attempt_ws(session_id: str, token: str | None) -> bool:
    """True iff the server actively refused the connection.

    A refused handshake (HTTP 403/404) or an immediate close is a rejection;
    any other failure (server down, timeout) is NOT counted as a rejection, so
    a dead server can't produce a false pass."""
    uri = f"{WS_BASE_URL}/ws/exam-sessions/{session_id}" + (f"?token={token}" if token else "")
    try:
        async with websockets.connect(uri, open_timeout=10) as ws:
            await ws.send(json.dumps({"type": "heartbeat"}))
            await asyncio.wait_for(ws.recv(), timeout=5)
            return False  # got a real heartbeat_ack for invalid credentials
    except websockets.exceptions.InvalidStatus as exc:
        return exc.response.status_code in (403, 404)
    except websockets.exceptions.ConnectionClosed:
        return True
    except Exception:  # noqa: BLE001
        return False


async def run_adversarial_sweep(target_session_id: str, seed: dict, repeats: int = 25) -> dict:
    tokens = {
        "no_token": None,
        "expired": create_access_token(
            data={"sub": str(seed["students"][0]["id"]), "role": "student"}, expires_delta=timedelta(seconds=-10)
        ),
        "unenrolled": create_access_token(data={"sub": str(seed["unenrolled_student_id"]), "role": "student"}),
        "wrong_exam": create_access_token(data={"sub": str(seed["wrong_exam_student_id"]), "role": "student"}),
    }
    attempts = [(case, token) for _ in range(repeats) for case, token in tokens.items()]
    outcomes = await asyncio.gather(*[attempt_ws(target_session_id, token) for _, token in attempts])
    by_case: dict[str, list[bool]] = {}
    for (case, _), rejected in zip(attempts, outcomes):
        by_case.setdefault(case, []).append(rejected)
    return {case: {"attempts": len(v), "all_rejected": all(v)} for case, v in by_case.items()}


async def adversarial_when_session_exists(student: dict, seed: dict) -> dict:
    for _ in range(60):
        async with async_session_maker() as db:
            found = (await db.execute(select(ExamSession).where(ExamSession.student_id == student["id"]))).scalars().first()
        if found is not None:
            return await run_adversarial_sweep(str(found.id), seed)
        await asyncio.sleep(1)
    return {"error": "target session never appeared"}


# ---------------------------------------------------------------------------
# Ground-truth DB assertions
# ---------------------------------------------------------------------------

async def count_exam_sessions(exam_id) -> int:
    async with async_session_maker() as db:
        return (await db.execute(select(func.count()).select_from(ExamSession).where(ExamSession.exam_id == exam_id))).scalar_one()


async def submission_status_counts(exam_id) -> dict[str, int]:
    async with async_session_maker() as db:
        rows = await db.execute(
            select(SubmissionQueueLog.status, func.count())
            .join(ExamSession, ExamSession.id == SubmissionQueueLog.session_id)
            .where(ExamSession.exam_id == exam_id)
            .group_by(SubmissionQueueLog.status)
        )
        return {status.value: count for status, count in rows.all()}


async def max_responses_per_student(exam_id) -> int:
    async with async_session_maker() as db:
        rows = await db.execute(
            select(func.count(QuizResponse.id))
            .join(ExamSession, ExamSession.id == QuizResponse.exam_session_id)
            .where(ExamSession.exam_id == exam_id)
            .group_by(ExamSession.student_id)
        )
        return max((count for (count,) in rows.all()), default=0)


async def wait_for_queue_drained(exam_id) -> dict[str, int]:
    deadline = time.monotonic() + DRAIN_TIMEOUT_SECONDS
    counts = await submission_status_counts(exam_id)
    while time.monotonic() < deadline:
        if counts.get(SubmissionStatus.pending.value, 0) + counts.get(SubmissionStatus.processing.value, 0) == 0:
            break
        await asyncio.sleep(2)
        counts = await submission_status_counts(exam_id)
    return counts


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(int(len(values) * p), len(values) - 1)]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def main(n_students: int, chaos: bool, adversarial: bool) -> dict:
    await wait_for_health()
    seed = await seed_load_test_data(n_students)
    exam_id, students = seed["exam_id"], seed["students"]
    print(f"[seed] exam_id={exam_id} students={n_students} questions={N_QUESTIONS}")

    adversarial_task = asyncio.create_task(adversarial_when_session_exists(students[0], seed)) if adversarial else None

    start_wall = time.monotonic()
    load_task = asyncio.create_task(run_load_simulation(students, exam_id))
    if chaos:
        await asyncio.sleep(2)
        print("[chaos] SIGKILL worker mid-run")
        docker_compose("kill", "-s", "SIGKILL", "worker")
        await asyncio.sleep(3)
        print("[chaos] restarting worker")
        docker_compose("up", "-d", "worker")
    results = await load_task
    wall = time.monotonic() - start_wall
    adversarial_result = await adversarial_task if adversarial_task else None

    counts = await wait_for_queue_drained(exam_id)
    session_count = await count_exam_sessions(exam_id)
    max_responses = await max_responses_per_student(exam_id)

    def by_phase(phase: str) -> list[RequestResult]:
        return [r for r in results if r.phase == phase]

    starts, submits = by_phase("start"), by_phase("submit")
    n_submitted_ok = sum(1 for r in submits if r.status == 202)
    failures = {
        "login_failures": len(by_phase("login")),
        "client_errors": [r.status for r in by_phase("client_error")],
        "ws_errors": len(by_phase("ws_error")),
    }
    assertions = {
        "session_count_ok": session_count == n_students,
        "all_starts_ok": sum(1 for r in starts if r.status == 200) == n_students,
        "all_submits_accepted": n_submitted_ok == n_students * N_QUESTIONS,
        "all_completed": counts.get("completed", 0) == n_submitted_ok and sum(counts.values()) == n_submitted_ok,
        "no_duplicate_processing": max_responses <= N_QUESTIONS,
        "no_client_failures": not failures["login_failures"] and not failures["client_errors"],
    }
    if adversarial_result is not None:
        assertions["adversarial_all_rejected"] = all(
            isinstance(v, dict) and v.get("all_rejected") for v in adversarial_result.values()
        )
    return {
        "n_students": n_students,
        "n_questions": N_QUESTIONS,
        "chaos": chaos,
        "wall_seconds": round(wall, 2),
        "exam_id": str(exam_id),
        "session_count": session_count,
        "submission_status_counts": counts,
        "max_responses_per_student": max_responses,
        "start_p95_seconds": round(percentile([r.elapsed for r in starts], 0.95), 3),
        "submit_p95_seconds": round(percentile([r.elapsed for r in submits], 0.95), 3),
        "failures": failures,
        "adversarial_sweep": adversarial_result,
        "assertions": assertions,
        "passed": all(assertions.values()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--students", type=int, default=50)
    parser.add_argument("--chaos", action="store_true", help="SIGKILL and restart the worker container mid-run")
    parser.add_argument("--adversarial", action="store_true", help="fire invalid-credential WebSocket attempts alongside the load")
    args = parser.parse_args()

    report = asyncio.run(main(args.students, args.chaos, args.adversarial))
    print(json.dumps(report, indent=2, default=str))
    sys.exit(0 if report["passed"] else 1)
