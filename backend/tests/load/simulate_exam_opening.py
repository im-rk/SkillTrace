"""
Phase 12 -- combined load + chaos test against a REAL running stack, not
pytest's per-session-wiped test DB (see tests/conftest.py's setup_db, which
drops the schema at session start/end; this script needs data that survives
across an entire run against real subprocesses).

This script is self-contained: it starts its own uvicorn, Celery worker, and
Redis-Stream consumer as subprocesses, seeds an exam directly via the app's
own DB session (bypassing HTTP for speed -- only the actual behavior under
test, start/WS/submit, goes over the wire), drives N students through it
concurrently, and asserts against real database state afterward -- never
just the script's own bookkeeping (a bug in this script could otherwise
produce a false "everything passed").

Usage (from backend/):
    uv run python -m tests.load.simulate_exam_opening --students 50
    uv run python -m tests.load.simulate_exam_opening --students 50 --chaos
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import websockets
from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BACKEND_DIR / "tests" / "load" / "_logs"
LOG_DIR.mkdir(exist_ok=True)

PROJECT_ROOT = BACKEND_DIR.parent
API_PORT = 8123
BASE_URL = f"http://127.0.0.1:{API_PORT}"
WS_BASE_URL = f"ws://127.0.0.1:{API_PORT}"
N_QUESTIONS = 20
STUDENT_PASSWORD = "LoadTestPassword123"

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


# --------------------------------------------------------------------------
# Seeding (direct DB session -- not HTTP; registration/exam-authoring isn't
# what this phase is testing, start/WS/submit under load is)
# --------------------------------------------------------------------------

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
    if qtype == "true_false":
        return "true"
    return "answer"


async def seed_load_test_data(n_students: int, n_questions: int = N_QUESTIONS):
    async with async_session_maker() as session:
        instructor = User(
            email=f"load_instr_{uuid.uuid4().hex[:8]}@example.com",
            display_name="Load Instructor",
            password_hash=get_password_hash("x"),
            role=UserRole.instructor,
        )
        skill = Skill(name="Load Test Skill", slug=f"load-{uuid.uuid4().hex[:8]}")
        session.add_all([instructor, skill])
        await session.commit()

        now = datetime.now(timezone.utc)
        exam = Exam(
            title="Load Test Exam",
            skill_id=skill.id,
            start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(hours=2),
            duration_minutes=120,
            created_by=instructor.id,
        )
        session.add(exam)
        await session.commit()

        questions = []
        for i in range(n_questions):
            qtype = QUESTION_TYPES[i % len(QUESTION_TYPES)]
            q = Question(
                skill_id=skill.id,
                question_type=qtype,
                prompt=f"Load test question {i}",
                difficulty=DifficultyLevel.easy,
                content=_question_content(qtype),
                created_by=instructor.id,
            )
            questions.append(q)
        session.add_all(questions)
        await session.commit()

        for i, q in enumerate(questions):
            session.add(
                ExamQuestion(exam_id=exam.id, question_id=q.id, question_version=1, display_order=i + 1, points=Decimal("1.0"))
            )
        await session.commit()

        students = []
        for i in range(n_students):
            student = User(
                email=f"load_student_{i}_{uuid.uuid4().hex[:6]}@example.com",
                display_name=f"Load Student {i}",
                password_hash=get_password_hash(STUDENT_PASSWORD),
                role=UserRole.student,
            )
            session.add(student)
            students.append(student)
        await session.commit()

        for student in students:
            session.add(ExamEnrollment(exam_id=exam.id, student_id=student.id))
        await session.commit()

        # An extra exam + student for the "wrong exam" adversarial case, and
        # one more student left deliberately unenrolled in the load exam.
        other_exam = Exam(
            title="Other Exam", skill_id=skill.id, start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(hours=2), duration_minutes=120, created_by=instructor.id,
        )
        session.add(other_exam)
        await session.commit()
        wrong_exam_student = User(
            email=f"load_wrongexam_{uuid.uuid4().hex[:6]}@example.com", display_name="Wrong Exam Student",
            password_hash=get_password_hash(STUDENT_PASSWORD), role=UserRole.student,
        )
        unenrolled_student = User(
            email=f"load_unenrolled_{uuid.uuid4().hex[:6]}@example.com", display_name="Unenrolled Student",
            password_hash=get_password_hash(STUDENT_PASSWORD), role=UserRole.student,
        )
        session.add_all([wrong_exam_student, unenrolled_student])
        await session.commit()
        session.add(ExamEnrollment(exam_id=other_exam.id, student_id=wrong_exam_student.id))
        await session.commit()

        return {
            "exam_id": exam.id,
            "students": [{"id": s.id, "email": s.email} for s in students],
            "wrong_exam_student_id": wrong_exam_student.id,
            "unenrolled_student_id": unenrolled_student.id,
        }


# --------------------------------------------------------------------------
# Subprocess orchestration
# --------------------------------------------------------------------------

def _log_file(name: str):
    return open(LOG_DIR / f"{name}.log", "w", encoding="utf-8")


def start_uvicorn() -> subprocess.Popen:
    return subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--port", str(API_PORT)],
        cwd=BACKEND_DIR, stdout=_log_file("uvicorn"), stderr=subprocess.STDOUT,
    )


def start_celery_worker() -> subprocess.Popen:
    return subprocess.Popen(
        ["uv", "run", "celery", "-A", "worker.celery_worker", "worker", "--loglevel=info", "--pool=solo"],
        cwd=BACKEND_DIR, stdout=_log_file("celery"), stderr=subprocess.STDOUT,
    )


def start_stream_consumer() -> subprocess.Popen:
    return subprocess.Popen(
        ["uv", "run", "python", "-m", "worker.stream_consumer"],
        cwd=BACKEND_DIR, stdout=_log_file("stream_consumer"), stderr=subprocess.STDOUT,
    )


def kill_process(proc: subprocess.Popen | None, graceful: bool = False) -> None:
    if proc is None or proc.poll() is not None:
        return
    if graceful:
        proc.terminate()
    else:
        proc.kill()  # hard kill -- simulates a real crash, not a clean shutdown
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


# --------------------------------------------------------------------------
# Docker mode -- run against `docker compose up backend worker
# stream_consumer` (Linux containers) instead of spawning native subprocesses.
# Native Windows execution of this stack hit a real asyncpg + ProactorEventLoop
# incompatibility under load (see docs/adr/0008-concurrency-testing-results.md);
# Docker sidesteps it entirely and is closer to how this would actually run
# in production anyway.
# --------------------------------------------------------------------------

def docker_compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], cwd=PROJECT_ROOT, capture_output=True, text=True)


def docker_kill_worker() -> None:
    docker_compose("kill", "-s", "SIGKILL", "worker")


def docker_restart_worker() -> None:
    docker_compose("up", "-d", "worker")


async def wait_for_health(timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                res = await client.get(f"{BASE_URL}/health", timeout=2.0)
                if res.status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError("uvicorn did not become healthy in time")


# --------------------------------------------------------------------------
# Load simulation
# --------------------------------------------------------------------------

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
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 -- recorded, not raised; a WS hiccup shouldn't kill the whole run
        results.append(RequestResult(email, "ws_error", str(exc)))


async def simulate_student(student: dict, exam_id: str, results: list[RequestResult]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        login_res = await client.post("/auth/login", json={"email": student["email"], "password": STUDENT_PASSWORD})
        if login_res.status_code != 200:
            results.append(RequestResult(student["email"], "login", login_res.status_code))
            return
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        t0 = time.monotonic()
        start_res = await client.post(f"/exams/{exam_id}/start", headers=headers)
        results.append(RequestResult(student["email"], "start", start_res.status_code, time.monotonic() - t0))
        if start_res.status_code != 200:
            return
        session_id = start_res.json()["session_id"]

        ws_task = asyncio.create_task(run_websocket(session_id, token, student["email"], results))

        questions_res = await client.get(f"/exams/{exam_id}/questions", headers=headers)
        questions = questions_res.json()["questions"] if questions_res.status_code == 200 else []

        for question in questions:
            answer = _pick_answer(question)
            t0 = time.monotonic()
            submit_res = await client.post(
                f"/exam-sessions/{session_id}/submit-answer",
                json={"question_id": question["question_id"], "answer": answer},
                headers=headers,
            )
            results.append(RequestResult(student["email"], "submit", submit_res.status_code, time.monotonic() - t0))

        await asyncio.sleep(1)
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass


async def run_load_simulation(students: list[dict], exam_id: str) -> list[RequestResult]:
    results: list[RequestResult] = []
    await asyncio.gather(*[simulate_student(s, exam_id, results) for s in students])
    return results


# --------------------------------------------------------------------------
# Adversarial sweep (Section 2.5/3.4) -- run interleaved with legitimate load
# --------------------------------------------------------------------------

async def attempt_ws(exam_session_id: str, token: str | None) -> bool:
    """Returns True iff the attempt was properly rejected (no functioning
    session was ever established)."""
    query = f"?token={token}" if token else ""
    uri = f"{WS_BASE_URL}/ws/exam-sessions/{exam_session_id}{query}"
    try:
        async with websockets.connect(uri, open_timeout=5) as ws:
            await ws.send(json.dumps({"type": "heartbeat"}))
            await asyncio.wait_for(ws.recv(), timeout=3)
            return False  # got a real heartbeat_ack -- should never happen for these credentials
    except Exception:  # noqa: BLE001 -- any failure to establish/use the connection counts as "rejected"
        return True


async def run_adversarial_sweep(exam_id: str, target_session_id: str, seed_data: dict, repeats: int = 25) -> dict:
    expired_token = create_access_token(
        data={"sub": str(seed_data["students"][0]["id"]), "role": "student"}, expires_delta=timedelta(seconds=-10)
    )
    unenrolled_token = create_access_token(data={"sub": str(seed_data["unenrolled_student_id"]), "role": "student"})
    wrong_exam_token = create_access_token(data={"sub": str(seed_data["wrong_exam_student_id"]), "role": "student"})

    attempts = ([("no_token", None)] + [("expired", expired_token)] + [("unenrolled", unenrolled_token)] + [("wrong_exam", wrong_exam_token)]) * repeats

    outcomes = await asyncio.gather(*[attempt_ws(target_session_id, token) for _, token in attempts])
    by_case: dict[str, list[bool]] = {}
    for (case, _), rejected in zip(attempts, outcomes):
        by_case.setdefault(case, []).append(rejected)
    return {case: {"attempts": len(v), "all_rejected": all(v)} for case, v in by_case.items()}


# --------------------------------------------------------------------------
# Ground-truth DB assertions (never trust this script's own bookkeeping alone)
# --------------------------------------------------------------------------

async def count_exam_sessions(exam_id) -> int:
    async with async_session_maker() as session:
        result = await session.execute(select(func.count()).select_from(ExamSession).where(ExamSession.exam_id == exam_id))
        return result.scalar_one()


async def submission_status_counts(exam_id) -> dict[str, int]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(SubmissionQueueLog.status, func.count())
            .join(ExamSession, ExamSession.id == SubmissionQueueLog.session_id)
            .where(ExamSession.exam_id == exam_id)
            .group_by(SubmissionQueueLog.status)
        )
        return {status.value: count for status, count in result.all()}


async def max_responses_per_student(exam_id) -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            select(ExamSession.student_id, func.count(QuizResponse.id))
            .join(QuizResponse, QuizResponse.exam_session_id == ExamSession.id)
            .where(ExamSession.exam_id == exam_id)
            .group_by(ExamSession.student_id)
        )
        counts = [count for _student_id, count in result.all()]
        return max(counts) if counts else 0


async def wait_for_queue_quiescent(exam_id, timeout: float = 90.0) -> dict[str, int]:
    deadline = time.monotonic() + timeout
    counts = await submission_status_counts(exam_id)
    while time.monotonic() < deadline:
        in_flight = counts.get(SubmissionStatus.pending.value, 0) + counts.get(SubmissionStatus.processing.value, 0)
        if in_flight == 0:
            return counts
        await asyncio.sleep(2)
        counts = await submission_status_counts(exam_id)
    return counts


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = min(int(len(values) * p), len(values) - 1)
    return values[idx]


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

async def main(n_students: int, chaos: bool, adversarial: bool, docker: bool) -> dict:
    global API_PORT, BASE_URL, WS_BASE_URL
    if docker:
        API_PORT = 8000
        BASE_URL = f"http://127.0.0.1:{API_PORT}"
        WS_BASE_URL = f"ws://127.0.0.1:{API_PORT}"

    seed_data = await seed_load_test_data(n_students)
    exam_id = seed_data["exam_id"]
    students = seed_data["students"]
    print(f"[seed] exam_id={exam_id} students={n_students} questions={N_QUESTIONS}")

    uvicorn_proc = celery_proc = consumer_proc = None
    if not docker:
        uvicorn_proc = start_uvicorn()
    try:
        await wait_for_health()
        if not docker:
            celery_proc = start_celery_worker()
            consumer_proc = start_stream_consumer()
            time.sleep(3)  # let both settle into steady state before the burst

        adversarial_task = None
        if adversarial:
            # A placeholder real session for the sweep to target; the first
            # legitimate student's session (created moments later by the
            # load run) is close enough in spirit to "attack a real session
            # id while it's in active legitimate use" -- fire it once that
            # student's session exists.
            async def delayed_adversarial_sweep():
                # Poll the DB directly for student[0]'s session to actually
                # exist -- /exams/{id}/results 404s immediately whether or
                # not a session exists yet (no results until the exam is
                # submitted and graded), so it can't be used as a readiness
                # signal here.
                session = None
                for _ in range(60):
                    async with async_session_maker() as s:
                        result = await s.execute(select(ExamSession).where(ExamSession.student_id == students[0]["id"]))
                        session = result.scalars().first()
                    if session is not None:
                        break
                    await asyncio.sleep(1)
                if session is None:
                    return {"skipped": "no session yet"}
                return await run_adversarial_sweep(exam_id, str(session.id), seed_data)

            adversarial_task = asyncio.create_task(delayed_adversarial_sweep())

        start_wall = time.monotonic()
        if chaos:
            load_task = asyncio.create_task(run_load_simulation(students, exam_id))
            await asyncio.sleep(2)
            print("[chaos] killing worker mid-run")
            if docker:
                docker_kill_worker()
            else:
                kill_process(celery_proc)
            await asyncio.sleep(3)
            print("[chaos] restarting worker")
            if docker:
                docker_restart_worker()
            else:
                celery_proc = start_celery_worker()
            time.sleep(2)
            results = await load_task
        else:
            results = await run_load_simulation(students, exam_id)
        wall_elapsed = time.monotonic() - start_wall

        adversarial_result = await adversarial_task if adversarial_task else None

        final_counts = await wait_for_queue_quiescent(exam_id)
        session_count = await count_exam_sessions(exam_id)
        max_responses = await max_responses_per_student(exam_id)

        starts = [r for r in results if r.phase == "start"]
        submits = [r for r in results if r.phase == "submit"]
        start_ok = [r for r in starts if r.status == 200]
        submit_ok = [r for r in submits if r.status == 202]

        report = {
            "n_students": n_students,
            "n_questions": N_QUESTIONS,
            "chaos": chaos,
            "wall_seconds": round(wall_elapsed, 2),
            "exam_id": str(exam_id),
            "assertions": {
                "session_count_expected": n_students,
                "session_count_actual": session_count,
                "session_count_ok": session_count == n_students,
                "submission_status_counts": final_counts,
                "stragglers_ok": final_counts.get("pending", 0) == 0 and final_counts.get("processing", 0) == 0,
                "max_responses_per_student": max_responses,
                "max_responses_ok": max_responses <= N_QUESTIONS,
            },
            "http": {
                "start_total": len(starts),
                "start_200": len(start_ok),
                "submit_total": len(submits),
                "submit_202": len(submit_ok),
                "start_p95_seconds": round(percentile([r.elapsed for r in starts], 0.95), 3),
                "submit_p95_seconds": round(percentile([r.elapsed for r in submits], 0.95), 3),
            },
            "adversarial_sweep": adversarial_result,
        }
        return report
    finally:
        kill_process(consumer_proc, graceful=True)
        kill_process(celery_proc, graceful=True)
        kill_process(uvicorn_proc, graceful=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--students", type=int, default=50)
    parser.add_argument("--chaos", action="store_true")
    parser.add_argument("--adversarial", action="store_true")
    parser.add_argument(
        "--docker", action="store_true",
        help="Run against `docker compose up -d backend worker stream_consumer` (already running) instead of "
        "spawning native subprocesses. Chaos mode then kills/restarts the `worker` container.",
    )
    args = parser.parse_args()

    report = asyncio.run(main(args.students, args.chaos, args.adversarial, args.docker))
    print(json.dumps(report, indent=2, default=str))
