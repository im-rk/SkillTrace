# SkillTrace — Demo Script

A walkthrough that shows **the whole product working, end to end**: an instructor builds a skill, its question bank and an exam; a student practises and takes the exam; the instructor reads the results. Each step lists the numbers the maths predicts, so you can say *"this is what the model says should happen"* and then show the screen agreeing.

**Time:** about 15 minutes (10 if you skip building the skill live and use the prepared *Fractions* data).

---

## 1. Start everything

Prerequisites: Docker Desktop running, Node 20+, [uv](https://docs.astral.sh/uv/).

```bash
# 1. Backend: PostgreSQL, Redis, API, Celery worker, Celery beat, stream consumer
docker compose up -d

# 2. Tables (first time) and demo data: 2 skills, 8 simulated students, a closed exam with results, a live exam
cd backend
uv run alembic upgrade head
uv run python -m scripts.demo_simulate        # prints the live-exam access code at the end

# 3. Frontend  ->  http://localhost:3000   (API http://localhost:8000, API docs /docs)
cd ../frontend
npm install                                   # first time only
npm run build; npm run start                  # on PowerShell use ';' instead of '&&'
```

Stop: `docker compose stop` and `Ctrl+C` in the frontend terminal. Start from nothing: `docker compose down -v`, then repeat from step 1.

**AI question drafting** (optional): put `GROQ_API_KEY=...` in a `.env` file at the repository root *before* `docker compose up`. Without it the "Draft with AI" panel says drafting is not switched on; everything else works.

### Accounts (password for all: `Passw0rd!demo`)

| Role | Email | Notes |
|---|---|---|
| Instructor | `instructor@skilltrace.dev` | Owns the skills, questions and exams |
| **Student (use live)** | `student@skilltrace.dev` | Has finished the midterm; **Decimals is untouched** (starts at 30 %); has **not** joined the live exam |
| Simulated classmates | `aarav@`, `diya@`, `kabir@`, `meera@`, `rohan@`, `sana@`, `vikram@skilltrace.dev` | Different abilities; they fill results and charts |

The **live exam access code** is printed at the end of `demo_simulate` (`live_access_code=...`). Lost it? Instructor → **Exams → Fractions Live Quiz → Generate access code**.

---

## 2. How it works, in one minute (say this first)

```
 Instructor                                   Student
 ──────────                                   ───────
 1 Create a SKILL  (a topic, e.g. Fractions)  ┐
 2 Fill its QUESTION BANK (easy/medium/hard)  ├─▶ Practice: each answer updates one number,
 3 Schedule an EXAM, pick questions,          │   "how likely is it that I know this skill"
   share an ACCESS CODE                       │   (mastery). That number picks the next
 4 Close the exam, read the RESULTS           ┘   question's difficulty, and stops at the goal.
```

- **Mastery** is a probability, not a score. It starts at **30 %** for a new student and moves after **every** answer, in practice *and* in exams (one shared estimate per student per skill).
- The model is **Bayesian Knowledge Tracing**: a correct answer could be a lucky *guess*, a wrong one could be a careless *slip*, so a single answer never takes mastery to 0 % or 100 %.
- Difficulty follows mastery: **below 40 % → easy**, **40–85 % → medium**, **85 % or more → mastered, practice ends**.

### Numbers to expect (default settings: start 0.30, learn 0.15, guess 0.20, slip 0.10, goal 0.85)

| Situation | Mastery shown |
|---|---|
| New student | **30 %** |
| After 1 correct answer | **71 %** |
| After 1 wrong answer (from 30 %) | **19 %** |
| Correct, correct | 71 % → **93 %** → *mastered* |
| Correct, wrong, correct | 71 % → 35 % → 75 % |
| Wrong, correct, wrong, correct, correct | 19 % → 59 % → 28 % → 69 % → **92 %** → mastered |

---

## 3. The demo

### Part A — The instructor builds a skill, its questions and an exam (≈ 5 min)

Log in as **instructor@skilltrace.dev**. The **Overview** page shows the four steps you are about to do, with live counts.

**A1. Create a skill.** *Skills → New skill.* Name `Percentages`, description `Finding a percentage of a number`. *Create skill.* You land inside the new skill, and the page already says **"Not ready yet — no easy or medium or hard questions"**. Say: *"Practice needs all three difficulties so it can adapt."*

**A2. Add its questions.** *Add question* (the editor stays open for the next one with *Save and add another*):

| Difficulty | Type | Question | Answer |
|---|---|---|---|
| Easy | Multiple choice | What is 10% of 50? | options `5`, `10`, `15`, `25` → mark **`5`** |
| Medium | True / false | 50% of 80 is 40. | **True** |
| Hard | Short answer | What is 15% of 240? | **36** |

Point out: *Save* stays disabled until every option is filled and one is marked correct. After the third question the page flips to **"Ready for practice and exams"**.

**A3. Draft more with AI (optional).** *Draft with AI* → focus `percentages of whole numbers` → *Draft questions*. A handful of drafts appear with their answers shown. Say: *"The AI only drafts. I read each answer, untick any I distrust, and only the ticked ones are saved. The mastery maths never involves the AI."* Tick two or three → *Save selected*; they appear tagged **AI-drafted**.

**A4. Look at the learning model.** *Learning model* tab. The five numbers are the model's knobs, with plain-language help. The panel on the right is a **live preview**: *starts at 30 %, after one correct answer 71 %, after one wrong 19 %, mastered after 2 correct in a row.* Change **Guess** from 0.20 to 0.05: one correct answer now jumps to about 90 %, because a lucky guess became unlikely. Click *Reset to defaults*.

**A5. Create the exam.** *Create an exam from this skill* (the skill is pre-selected). Title `Percentages quiz`, click **Open now for 3 hours**, duration `20`, *Create exam*.

**A6. Choose questions and get the code.** On the exam page tick all the percentage questions → *Save questions* → **Generate access code**. The checklist at the top turns green as you go. Keep the big code on screen.

*Shows: roles, skills, readiness check, question editor (3 types), AI drafting with human review, learning-model preview, exam scheduling, access codes.*

> **Shortcut:** skip A1–A3 and use the prepared **Fractions** skill (18 questions) and its **Fractions Live Quiz**, whose code `demo_simulate` printed.

### Part B — A student practises and BKT moves (≈ 4 min)

Log in as **student@skilltrace.dev** (or *Register* a fresh student to show sign-up).

1. **Dashboard** → *Your skills*: Fractions is **Mastered**, Decimals is **Not started**. *Start practice* on **Decimals**.
2. The mastery panel shows **30 %**, the goal tick at 85 %, and an **easy** question.
3. Answer **correctly** → feedback **"Mastery 30% → 71%"** and a green ▲ 41. Say: *"A correct answer is far more likely from someone who knows the skill than from a guesser, so belief jumps."*
4. *Next question*. Answer **wrongly** → mastery falls (71 % → 35 %), but not to zero. Say: *"Even a student who knows it slips sometimes."* Watch the difficulty change as mastery crosses 40 %.
5. Keep answering correctly until **"You've mastered this skill!"** (≥ 85 %).
6. **My progress** → Decimals. The chart shows mastery after every answer: ● correct, ✕ incorrect, the dashed **Goal** line, and a vertical line **"Likely mastered here"**. Say: *"The curve is the running belief; the vertical line is a second algorithm (Viterbi) that looks at the whole history and says when learning most likely happened."* Open *Show answer-by-answer table* for the exact numbers.

*Shows: BKT forward update with exact numbers, difficulty adaptation, goal stop, Viterbi marker, progress chart, shared mastery chain.*

### Part C — The student takes the timed exam (≈ 3 min)

Still as the student: **Join exam** → enter the code from A6 (or the Fractions one) → *Join exam*.

1. The exam opens with a **server-synchronised countdown** and "0 of N answered".
2. Answer a few questions; each shows **"Answer recorded"** once the background worker has graded it. Say: *"The answer is saved to PostgreSQL first and queued second, so it cannot be lost even if a worker dies."*
3. An answered question is **final**.
4. *Finish exam → Yes, submit.* Reloading shows "already finished": one attempt only.
5. *(Optional)* open another student's exam and wait out the clock: the server **auto-submits** and pushes "Time is up".

*Shows: access codes, enrolment, exam window, one attempt, WebSocket clock, durable grading pipeline, auto-submit.*

### Part D — The instructor reads the results (≈ 3 min)

Back as the instructor: *Exams → Fractions Midterm Quiz → View results overview* (the closed exam with 8 simulated students). For your own exam, press **Close exam** first; results are computed on close.

1. **Four tiles** summarise the class (students, average score, average mastery, questions to review).
2. **Students** table: score *and* mastery side by side, e.g. Aarav 12 / 100 %, Rohan 3 / 42 %, Vikram 2 / 27 %. Say: *"Score counts points in this exam; mastery is built from all of a student's answers, including practice."*
3. **Item analysis**: for each question, how many got it right (difficulty) and its **discrimination** (top 27 % minus bottom 27 %). The *"What is 2/3 + 1/6?"* row is **weak (0.00)**: almost everyone got it right, so it tells the instructor nothing. Say: *"This is how the instructor finds questions to fix."*
4. *Audit trail* on a student: everything recorded in their attempt.
5. As the student: *Dashboard → My exams → View results* shows their own score and a mastery ring.

*Shows: precomputed results (materialized view), item analysis, audit trail, student results.*

### Part E — Proof it is correct (≈ 2 min, terminal)

```bash
cd backend  && uv run pytest -q          # 293 tests against a real PostgreSQL and Redis
cd frontend && npm run e2e                # 9 real-browser journeys, including the instructor building a skill and exam from nothing
```

Also worth showing: the API docs at **http://localhost:8000/docs**; the BKT engine in `backend/app/modules/quiz_engine/domain/bkt/` (about 380 lines of plain Python, no ML library); and `uv run python -m scripts.recompute_mastery --all --dry-run`, which rebuilds every student's mastery from the answer log and checks it matches.

---

## 4. Feature checklist

| # | Feature | Where shown |
|---|---|---|
| 1 | Registration, login, roles | Login page; menus differ per role |
| 2 | Skills, readiness check | A1, A2 |
| 3 | Question editor (3 types) with validation | A2 |
| 4 | AI question drafting with human review | A3 |
| 5 | Learning-model settings with live preview | A4 |
| 6 | Exam scheduling, question picker, access codes | A5, A6 |
| 7 | Adaptive practice with live mastery | B2–B5 |
| 8 | BKT forward update (exact numbers) | B3, B4 |
| 9 | Difficulty policy and goal stop | B4, B5 |
| 10 | Viterbi "likely mastered here" | B6 |
| 11 | Timed exam, server clock, WebSocket | C1 |
| 12 | Durable grading pipeline | C2 |
| 13 | One attempt, final answers, auto-submit | C3–C5 |
| 14 | Results with score and mastery | D1, D2 |
| 15 | Item analysis | D3 |
| 16 | Audit trail | D4 |
| 17 | Automated verification | E |

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| Page loads but shows errors / CORS | The frontend was built for another API address. Rebuild: `npm run build` (it reads `frontend/.env.local`, `http://localhost:8000`) |
| `localhost:8000` unreachable | `docker compose up -d`, wait ~10 s, `curl localhost:8000/health` → `{"status":"ok"}`. Another program may hold port 8000 |
| Docker commands hang | Restart Docker Desktop, then `docker compose up -d` |
| "Too many requests" on login | Login is limited to 30 per minute per IP; wait a minute |
| "Exam is not currently open" | The prepared live exam opens 1 hour before and closes 8 hours after `demo_simulate` ran; re-run it, or make a new exam with *Open now* |
| Access code rejected | Generate a new one on the exam page |
| Empty screens | `uv run python -m scripts.demo_simulate` (safe to re-run) |
| "Draft with AI" says not switched on | Add `GROQ_API_KEY` to the root `.env` and restart the backend containers |

---

## 6. One-line talking points

- *"BKT turns a stream of right and wrong answers into a probability of mastery, and that probability decides the next question."*
- *"The inference is exact, constant work per answer, and written from scratch: no library."*
- *"Every answer is stored with the parameters used, so any mastery number can be rebuilt and audited."*
- *"The same estimate is shared by practice and exams."*
- *"Answers are committed before they are queued, so a crash cannot lose them."*
- *"AI drafts questions; a human approves them; the mastery maths never uses AI."*
