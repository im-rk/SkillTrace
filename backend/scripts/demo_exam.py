"""
Seeds the demo accounts + question pool, then schedules a demo exam through the API.

    uv run python -m scripts.demo_exam 09:45        # starts today at 09:45 local, runs 3h

Prints the logins and the access code a student redeems to enrol.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.seed_demo import DEMO_PASSWORD, INSTRUCTOR_EMAIL, seed  # noqa: E402

API = "http://localhost:8000"


async def main(start_hhmm: str) -> None:
    info = await seed()
    hour, minute = map(int, start_hhmm.split(":"))
    start = datetime.now().astimezone().replace(hour=hour, minute=minute, second=0, microsecond=0)
    async with httpx.AsyncClient(base_url=API, timeout=30) as c:
        login = await c.post("/auth/login", json={"email": INSTRUCTOR_EMAIL, "password": DEMO_PASSWORD})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        exam = (await c.post("/exams", headers=headers, json={
            "title": f"Fractions demo exam ({start_hhmm})", "description": "Manual BKT check",
            "skill_id": info["skill_id"], "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=3)).isoformat(), "duration_minutes": 30,
        })).json()
        questions = (await c.get("/question-bank/questions", headers=headers, params={"skill_id": info["skill_id"]})).json()
        items = questions["items"] if isinstance(questions, dict) else questions
        (await c.post(f"/exams/{exam['id']}/questions", headers=headers, json={
            "questions": [{"question_id": q["id"], "display_order": i + 1} for i, q in enumerate(items)],
        })).raise_for_status()
        code = (await c.post(f"/exams/{exam['id']}/access-codes", headers=headers, json={})).json()
    print(f"exam_id={exam['id']}  starts={start:%H:%M}  questions={len(items)}")
    print(f"access_code={code['code']}")
    print(f"student   {info['student']} / {DEMO_PASSWORD}")
    print(f"instructor {INSTRUCTOR_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "09:45"))
