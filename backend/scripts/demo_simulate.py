"""
Fills a fresh stack with realistic demo activity through the public API, so every screen has data.

    uv run python -m scripts.demo_simulate

What it creates (idempotent -- safe to re-run):
  * a second skill, "Decimals" (12 questions), left untouched so a live demo can start from 30 % mastery
  * 8 simulated students of different ability, each with adaptive-practice history on Fractions
  * "Fractions Midterm Quiz": taken and submitted by all 8, then closed -> results + item analysis
  * "Fractions Live Quiz": open right now, nobody has taken it -> use it for the live exam demo
Prints a fresh access code for the live exam every run.
"""
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.seed_demo import (  # noqa: E402
    DEMO_PASSWORD, E, H, INSTRUCTOR_EMAIL, M, QUESTIONS, STUDENT_EMAIL, _mcq, _text, _tf, seed,
)

API = "http://localhost:8000"
DECIMALS = [
    _mcq("What is 0.5 + 0.25?", ["0.75", "0.30", "0.55", "0.7"], 0, E),
    _tf("0.5 is equal to 1/2.", True, E),
    _text("What is 0.1 + 0.2?", "0.3", E),
    _mcq("Which is the largest?", ["0.09", "0.9", "0.19", "0.099"], 1, E),
    _mcq("What is 1.5 x 2?", ["3", "2.5", "3.5", "30"], 0, M),
    _tf("0.30 is greater than 0.3.", False, M),
    _text("What is 7.5 divided by 5?", "1.5", M),
    _mcq("Round 3.14159 to two decimal places.", ["3.14", "3.15", "3.1", "3.142"], 0, M),
    _mcq("What is 0.04 x 0.5?", ["0.02", "0.2", "0.002", "2"], 0, H),
    _tf("0.1 x 0.1 = 0.1", False, H),
    _text("What is 2.5 squared?", "6.25", H),
    _mcq("What is 12.6 / 0.3?", ["42", "4.2", "420", "38"], 0, H),
]
STUDENTS = [  # (email, name, ability) -- STUDENT_EMAIL is the account used in live demos
    (STUDENT_EMAIL, "Demo Student", 0.70),
    ("aarav@skilltrace.dev", "Aarav Menon", 0.95),
    ("diya@skilltrace.dev", "Diya Nair", 0.88),
    ("kabir@skilltrace.dev", "Kabir Shah", 0.80),
    ("meera@skilltrace.dev", "Meera Iyer", 0.62),
    ("rohan@skilltrace.dev", "Rohan Das", 0.50),
    ("sana@skilltrace.dev", "Sana Khan", 0.42),
    ("vikram@skilltrace.dev", "Vikram Rao", 0.30),
]
EXAM_PLAN = [  # (difficulty, how many) for each exam's question set
    ("easy", 4), ("medium", 4), ("hard", 4),
]
rng = random.Random(2026)


def p_correct(ability: float, difficulty: str) -> float:
    return min(0.98, max(0.05, ability + {"easy": 0.15, "medium": 0.0, "hard": -0.25}[difficulty]))


def answer_for(question: dict, right: bool) -> str:
    """question: a stored question (with `content` incl. the key) -> submitted string."""
    c, t = question["content"], question["question_type"]
    if t == "multiple_choice":
        if right:
            return c["correct_choice_id"]
        return next(ch["id"] for ch in c["choices"] if ch["id"] != c["correct_choice_id"])
    if t == "true_false":
        return str(c["correct_answer"] if right else not c["correct_answer"]).lower()
    return c["correct_answer"] if right else "zzz"


async def login(c: httpx.AsyncClient, email: str, name: str | None = None) -> dict:
    if name:
        await c.post("/auth/register", json={"email": email, "password": DEMO_PASSWORD, "display_name": name})
    res = await c.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    res.raise_for_status()
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def ensure_decimals(c: httpx.AsyncClient, ih: dict) -> None:
    skills = (await c.get("/skills", headers=ih)).json()
    if any(s["slug"] == "decimals" for s in skills):
        return
    skill = (await c.post("/skills", headers=ih, json={"name": "Decimals", "slug": "decimals", "description": "Adding, rounding and comparing decimals"})).json()
    for q in DECIMALS:
        body = {**q, "skill_id": skill["id"], "question_type": q["question_type"].value, "difficulty": q["difficulty"].value}
        (await c.post("/question-bank/questions", headers=ih, json=body)).raise_for_status()


async def practise(c: httpx.AsyncClient, headers: dict, skill_id: str, ability: float, max_answers: int, quit_after: bool, pattern: list[bool] | None = None) -> None:
    session = (await c.post("/quiz-sessions", headers=headers, json={"skill_id": skill_id})).json()
    sid, done = session["id"], 0
    while done < max_answers:
        nxt = (await c.get(f"/quiz-sessions/{sid}/next-question", headers=headers)).json()
        if nxt["status"] != "in_progress":
            return
        q = nxt["question"]
        right = pattern[done] if pattern else rng.random() < p_correct(ability, q["difficulty"])
        # The student view hides the key, so look it up on the bank copy (instructor-visible) by id.
        res = await c.post(f"/quiz-sessions/{sid}/answer", headers=headers, json={"question_id": q["id"], "submitted_answer": KEY[q["id"]](right)})
        done += 1
        if res.json()["session_status"] != "in_progress":
            return
    if quit_after:
        await c.post(f"/quiz-sessions/{sid}/quit", headers=headers)


KEY: dict = {}  # question id -> callable(right) -> submitted answer


async def pick_exam_questions(c: httpx.AsyncClient, ih: dict, skill_id: str) -> list[dict]:
    bank = (await c.get("/question-bank/questions", headers=ih, params={"skill_id": skill_id})).json()
    picked = []
    for difficulty, n in EXAM_PLAN:
        picked += [q for q in bank if q["difficulty"] == difficulty][:n]
    return picked


async def create_exam(c: httpx.AsyncClient, ih: dict, title: str, skill_id: str, questions: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    exam = (await c.post("/exams", headers=ih, json={
        "title": title, "description": "Mixed-difficulty fractions quiz", "skill_id": skill_id,
        "start_time": (now - timedelta(hours=1)).isoformat(), "end_time": (now + timedelta(hours=8)).isoformat(), "duration_minutes": 30,
    })).json()
    (await c.post(f"/exams/{exam['id']}/questions", headers=ih, json={
        "questions": [{"question_id": q["id"], "display_order": i + 1} for i, q in enumerate(questions)],
    })).raise_for_status()
    return exam["id"]


async def access_code(c: httpx.AsyncClient, ih: dict, exam_id: str) -> str:
    return (await c.post(f"/exams/{exam_id}/access-codes", headers=ih, json={})).json()["code"]


async def take_exam(c: httpx.AsyncClient, headers: dict, exam_id: str, code: str, questions: list[dict], ability: float) -> list[tuple[dict, str]]:
    (await c.post(f"/access-codes/{code}/redeem", headers=headers)).raise_for_status()
    session = (await c.post(f"/exams/{exam_id}/start", headers=headers)).json()
    log_ids = []
    for q in questions:
        right = rng.random() < p_correct(ability, q["difficulty"])
        res = await c.post(f"/exam-sessions/{session['session_id']}/submit-answer", headers=headers,
                           json={"question_id": q["id"], "answer": answer_for(q, right)})
        res.raise_for_status()
        log_ids.append((headers, res.json()["log_id"]))
        await asyncio.sleep(0.4)  # a human is never faster than this; also keeps grading in order
    (await c.post(f"/exam-sessions/{session['session_id']}/submit", headers=headers)).raise_for_status()
    return log_ids


async def main() -> None:
    info = await seed()
    async with httpx.AsyncClient(base_url=API, timeout=60) as c:
        ih = await login(c, INSTRUCTOR_EMAIL)
        await ensure_decimals(c, ih)
        skills = {s["slug"]: s for s in (await c.get("/skills", headers=ih)).json()}
        fractions = skills["fractions"]["id"]

        bank = []
        for skill in skills.values():
            bank += (await c.get("/question-bank/questions", headers=ih, params={"skill_id": skill["id"]})).json()
        for q in bank:
            KEY[q["id"]] = lambda right, q=q: answer_for(q, right)

        exams = {e["title"]: e for e in (await c.get("/exams", headers=ih)).json()}
        questions = await pick_exam_questions(c, ih, fractions)

        if "Fractions Midterm Quiz" not in exams:
            student_headers = {email: await login(c, email, name) for email, name, _ in STUDENTS}
            # Practice history first, so the instructor's mastery table and progress charts are populated.
            for email, _, ability in STUDENTS:
                demo = email == STUDENT_EMAIL
                await practise(c, student_headers[email], fractions, ability, max_answers=5 if demo else 10, quit_after=True,
                               pattern=[False, True, False, True, False] if demo else None)
            exam_id = await create_exam(c, ih, "Fractions Midterm Quiz", fractions, questions)
            code = await access_code(c, ih, exam_id)
            log_ids = []
            for email, _, ability in STUDENTS:
                log_ids += await take_exam(c, student_headers[email], exam_id, code, questions, ability)
            for _ in range(90):  # wait for the workers to grade everything before closing
                done = [(await c.get(f"/submissions/{lid}", headers=h)).json()["status"] == "completed" for h, lid in log_ids]
                if all(done):
                    break
                await asyncio.sleep(1)
            (await c.post(f"/exams/{exam_id}/close", headers=ih)).raise_for_status()
            print("midterm simulated and closed:", exam_id)

        if "Fractions Live Quiz" not in exams:
            live_id = await create_exam(c, ih, "Fractions Live Quiz", fractions, questions)
        else:
            live_id = exams["Fractions Live Quiz"]["id"]
        print(f"live_exam_id={live_id}")
        print(f"live_access_code={await access_code(c, ih, live_id)}")
        print(f"student   {STUDENT_EMAIL} / {DEMO_PASSWORD}   (more: aarav@, diya@, kabir@, meera@, rohan@, sana@, vikram@skilltrace.dev)")
        print(f"instructor {INSTRUCTOR_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
