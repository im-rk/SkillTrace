# SkillTrace — Demo Script

A step-by-step walkthrough that shows **every feature** of SkillTrace working, in about **12–15 minutes**, with the expected numbers so you can say *"this is what the maths predicts"* and then show the screen agreeing.

---

## 1. Start everything

Prerequisites: Docker Desktop running, Node 20+ and [uv](https://docs.astral.sh/uv/) installed.

```bash
# 1. Backend stack: PostgreSQL, Redis, API, Celery worker, Celery beat, stream consumer
docker compose up -d

# 2. Create the tables (first time only) and fill the app with realistic demo data
cd backend
uv run alembic upgrade head
uv run python -m scripts.demo_simulate        # prints the live-exam access code at the end

# 3. Frontend
cd ../frontend
npm install                                   # first time only
npm run build && npm run start                # http://localhost:3000   (API: http://localhost:8000, docs: /docs)
```

To stop: `docker compose stop` and close the frontend terminal (`Ctrl+C`).
To start over from nothing: `docker compose down -v` and repeat from step 1.

### Credentials (password for every account: `Passw0rd!demo`)

| Role | Email | Notes |
|---|---|---|
| Instructor | `instructor@skilltrace.dev` | Owns the skills, questions and exams |
| **Student (use this one live)** | `student@skilltrace.dev` | Has a finished midterm; **Decimals is untouched** → starts at 30 %; **has not joined the live exam yet** |
| Simulated classmates | `aarav@`, `diya@`, `kabir@`, `meera@`, `rohan@`, `sana@`, `vikram@skilltrace.dev` | Different abilities; they populate results and charts |

The **live-exam access code** is printed by `demo_simulate` (look for `live_access_code=…`). If you lose it, log in as the instructor → **Exams → Fractions Live Quiz → Generate access code**.

### What the demo data contains

| Item | Details |
|---|---|
| Skills | **Fractions** (18 questions) and **Decimals** (12 questions), each with easy / medium / hard questions |
| Class | 8 students with different abilities and practice history on Fractions |
| **Fractions Midterm Quiz** | Taken by all 8 students (12 questions), **closed** → results and item analysis exist |
| **Fractions Live Quiz** | **Open right now**, 30 minutes per attempt, nobody has taken it → use it for the live exam demo |

---

## 2. The numbers to expect (BKT with the default parameters)

Defaults: P(L0)=0.30, P(T)=0.15, P(G)=0.20, P(S)=0.10, mastery threshold 0.85.

| Situation | Mastery shown |
|---|---|
| Fresh student, no answers | **30 %** |
| After 1 correct answer | **71 %** (0.7098) |
| After 1 wrong answer (from 30 %) | **19 %** (0.1932) |
| ✔ then ✔ | 71 % → **93 %** → *mastered* (≥ 85 %) |
| ✔ ✘ ✔ | 71 % → 35 % → 75 % |
| ✘ ✔ ✘ ✔ ✔ | 19 % → 59 % → 28 % → 69 % → **92 %** → mastered |

Difficulty policy: mastery **< 40 %** → easy questions; **40 %–85 %** → medium; **≥ 85 %** → mastered, session ends.

---

## 3. The demo, step by step

### Part A — Instructor view (≈ 3 min)  *login as the instructor*

1. **Skills page** (`Skills` in the menu) → choose **Decimals**.
   - Show the BKT parameters (initial knowledge, learning rate P(T), guess P(G), slip P(S)) and the **mastery threshold** — *these are the model's knobs, editable per skill*.
   - Show the **readiness** line: the skill has easy, medium and hard questions, so adaptive practice is possible.
   - Show the **class mastery table** below: each student's current mastery, attempts and mastered flag.
2. **Question bank** → show the questions by skill and difficulty and the three question types (multiple choice, true/false, text input). **Generate with AI** *(needs `GROQ_API_KEY` in `.env`)*: pick Decimals, 5 questions, mixed, focus "rounding", click **Generate with AI** → review the drafts (the answer is shown beside each), untick any you dislike, **Save selected**. Say: *"the LLM only drafts; the instructor approves, and the mastery maths never involves the LLM."* Also mention that **bulk import** (CSV/JSON, with a per-row success/failure report) is available through the API — open `http://localhost:8000/docs` → `question-bank` → `bulk-import`.
3. **Exams** → open **Fractions Live Quiz**: assigned questions, the access code, the *Close exam* button, and the derived phase (**live**).

*Features shown: role-based access, skill & BKT configuration, readiness check, question bank, bulk import, exam scheduling, access codes.*

### Part B — Adaptive practice and BKT (≈ 4 min)  *login as `student@skilltrace.dev`*

1. **Practice** → the list shows **Fractions: Mastered** and **Decimals: Not started**. Click **Start practice** on Decimals.
2. The first question is **easy** and the gauge reads **30 %** (the prior P(L0)).
3. Answer **correctly** → feedback shows **"Mastery 30% → 71%"**. Say: *"a correct answer is much more likely from someone who knows the skill than from a guesser, so belief jumps."*
4. Click **Next question**. Answer **wrongly** → mastery falls (71 % → 35 %). Say: *"a wrong answer lowers belief, but not to zero, because even masters slip."* Watch the **difficulty change** between questions as mastery crosses 40 %.
5. Keep answering correctly until the **"You've mastered this skill"** screen appears (≥ 85 %).
6. Open **My progress** → choose Decimals → the chart shows mastery after every answer, the **85 % goal line**, and the purple **"Likely mastered here"** marker. Say: *"the curve is forward filtering — the belief at each moment. The marker is Viterbi decoding — the single most likely moment learning actually happened, looking at the whole history."*

*Features shown: BKT forward update, adaptive difficulty policy, mastery threshold stop, Viterbi trajectory, progress chart, shared mastery chain.*

> **Optional what-if (1 min):** as the instructor, set Decimals' **Guess P(G)** from 0.20 to 0.05 and save. Start a *new* student session — a single correct answer now jumps to **≈ 90 %** instead of 71 % (a lucky guess is now much less likely, so a correct answer is stronger evidence). Set it back to 0.20 afterwards.

### Part C — Taking a timed exam (≈ 3 min)  *still the student*

1. **Join exam** → enter the access code → **Join exam**. (A wrong code is rejected; redemption is rate-limited to 5 attempts a minute.)
2. The exam opens with a **server-synchronised countdown** (30:00). Answer a few questions; each shows **"Answer recorded"** once the background worker has graded it. Say: *"the answer was saved to PostgreSQL first, queued second — it can't be lost, even if a worker dies."*
3. An answered question is **final** (its button disables).
4. Click **Finish exam → Yes, submit**. Reloading the page shows the exam is already finished — no second attempt.
5. *(Optional, no extra setup)* leave a different student's exam open past its limit: the server **auto-submits** and pushes a "Time is up" message over the WebSocket.

*Features shown: access codes, enrolment, exam window check, distributed start lock, WebSocket session, durable submission pipeline, async grading, BKT update inside the exam, auto-submit.*

### Part D — Results and analytics (≈ 2 min)  *login as the instructor*

1. **Exams → Fractions Midterm Quiz → Results**.
   - **Results overview**: every student's score and mastery — e.g. Aarav 12 / 100 %, Rohan 3 / 42 %, Vikram 2 / 27 %. Say: *"two students with the same score can have different mastery, because order and difficulty matter."*
2. **Item analysis** (below): for each question, **difficulty** (p-value = fraction correct) and **discrimination** (top 27 % minus bottom 27 % correct rate), labelled strong or weak. Point at a **weak** question (discrimination 0.00) — *"this question doesn't separate strong from weak students; the instructor should review it."*
3. Click **Audit trail** for a student → the timeline of events for that exam session.
4. Back as the student → **My exams → View results** shows their own score.

*Features shown: precomputed results (materialized view), item analysis, audit trail, per-student results.*

### Part E — Proof that it is correct (≈ 2 min, terminal)

```bash
cd backend && uv run pytest -q          # 278 passed  (real PostgreSQL + Redis)
cd ../frontend && npm run e2e            # 6 passed    (real browser, real backend)
```

Also worth showing:
- API documentation at **http://localhost:8000/docs**.
- `backend/app/modules/quiz_engine/domain/bkt/` — the whole BKT engine in ~380 lines of pure Python, no ML library: `engine.py` (forward update), `viterbi.py`, `policy.py`, `params.py`.
- Rebuild proof: `uv run python -m scripts.recompute_mastery --all --dry-run` recomputes every student's mastery from the immutable answer log and reports whether it reproduces the stored values.

---

## 4. Feature checklist (tick as you show it)

| # | Feature | Where shown |
|---|---|---|
| 1 | Registration, login, roles (student / instructor) | Login page, menus differ per role |
| 2 | Skills with editable BKT parameters and threshold | A.1 |
| 3 | Question bank, 3 question types (bulk import via API) | A.2 |
| 4 | Exam creation, question assignment, access codes | A.3 |
| 5 | Adaptive practice with live mastery gauge | B.2–B.5 |
| 6 | BKT forward update (exact numbers) | B.3, B.4 |
| 7 | Difficulty adaptation policy | B.4 |
| 8 | Viterbi "likely mastered here" | B.6 |
| 9 | Timed exam, server countdown, WebSocket | C.2 |
| 10 | Durable async grading pipeline | C.2 |
| 11 | One attempt per student, final answers | C.3, C.4 |
| 12 | Auto-submit on time-out | C.5 |
| 13 | Results, mastery per student | D.1 |
| 14 | Item analysis (difficulty, discrimination) | D.2 |
| 15 | Audit trail | D.3 |
| 16 | Automated verification (278 + 6 tests) | E |

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `localhost:8000` not reachable | `docker compose up -d`; wait ~10 s; `curl localhost:8000/health` should return `{"status":"ok"}` |
| Docker commands hang | Restart Docker Desktop, then `docker compose up -d` |
| Login says "too many requests" | Login is limited to 30 per minute per IP — wait a minute |
| "Exam is not currently open" | The Live Quiz window is 1 hour before to 8 hours after the time `demo_simulate` ran; re-run it after that |
| Access code rejected | Generate a new one: instructor → Exams → Fractions Live Quiz → *Generate access code* |
| Empty screens | Run `uv run python -m scripts.demo_simulate` (safe to re-run; it only adds what is missing) |
| Port 3000 busy | Stop the process using port 3000 — the API only accepts requests from the frontend origin `http://localhost:3000` |

---

## 6. One-line talking points

- *"BKT turns a stream of right/wrong answers into a probability of mastery — and that probability decides the next question."*
- *"The inference is exact, O(1) per answer, and implemented from scratch — no library."*
- *"Every answer is stored with the parameters used, so any student's mastery can be rebuilt and audited."*
- *"The same mastery chain is shared by practice and exams."*
- *"Answers are committed before they are queued, so a crash cannot lose them."*
