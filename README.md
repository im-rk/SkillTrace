# SkillTrace

An adaptive exam and practice platform that tracks student mastery with real Bayesian inference (Bayesian Knowledge Tracing), delivered through a distributed system built to survive the moment that actually breaks these platforms: everyone hitting it at once.

## What makes this interesting

- **The mastery number is a real probability, derived and explainable, not a score.** Every answer runs the exact BKT forward algorithm — a Bayesian posterior update followed by a learning-transition step — against parameters snapshotted at submission time (not re-read later), so a mid-exam parameter edit can never retroactively change how an already-submitted answer was scored. `mastery_before`/`mastery_after` are stored on every single response, so any mastery number in the system can always be traced back to the exact sequence of answers that produced it — and that claim isn't just asserted: `scripts/recompute_mastery.py` deletes a student's cached mastery and rebuilds it from nothing but the raw answer log, byte-for-byte identical, as an executable proof.
- **Mastery is one chain, shared by exams and free practice, correct under real concurrency.** A student's mastery for a skill is a single row, updated by whichever grading path touches it next — an exam answer graded by a Celery worker, or a free-practice answer graded synchronously. Two updates racing for the same row is not a hypothetical: it's tested by literally firing them concurrently (`asyncio.gather`) and asserting the chain isn't broken, with the row lock removed first to confirm the test actually catches the bug it claims to.
- **A durable queue absorbs the thundering herd at "time's up."** When an exam's timer hits zero, every connected student submits within the same second. The fast path writes one row to Postgres and commits — the actual durability guarantee — *before* pushing to a Redis Stream for async grading; if the process dies after that commit, the submission is a `pending` row a recovery sweep finds and redispatches, never silently lost. A consumer group (not a plain queue) means a crashed worker's in-flight message is reclaimable, not gone.
- **WebSocket authorization resolves before the connection ever accepts.** Every live exam-session connection is authorized (enrolled? this session's own owner? session still active?) *before* `websocket.accept()` is called — not accepted-then-closed. This is enforced by a test that asserts `accept()`'s call count is literally zero for every rejection path, the one check that actually catches the "accept, then decide" bug class a close-code-only test would miss.

## Architecture

```
                              ┌──────────────┐
  student / instructor  ────▶ │  Next.js app │
       (browser)              └──────┬───────┘
                                      │ HTTPS + WSS
                                      ▼
                          ┌───────────────────────┐
                          │      FastAPI API        │
                          │ (request/response, WS)  │
                          └───────────┬─────────────┘
                                      │
                ┌─────────────────────┼───────────────────────┐
                ▼                     ▼                       ▼
        ┌──────────────┐      ┌─────────────┐         ┌──────────────┐
        │  PostgreSQL   │◀────▶│    Redis     │◀───────▶│ Celery worker │
        │ (source of    │      │ locks, pub/  │         │  (grading:    │
        │  truth)       │      │ sub, streams │         │  BKT engine)  │
        └──────────────┘      └──────┬──────┘         └──────────────┘
                                      │
                          ┌───────────┴────────────┐
                          ▼                         ▼
                 ┌────────────────┐        ┌────────────────┐
                 │ stream_consumer │        │  Celery Beat    │
                 │ (dispatches     │        │ (stale-session, │
                 │  graded work)   │        │  auto-submit,   │
                 └────────────────┘        │  auto-close)     │
                                            └────────────────┘
```

Backend: a modular monolith (one FastAPI codebase, split into domain modules — `iam`, `question_bank`, `scheduling`, `enrollment`, `live_session_gateway`, `evaluation_pipeline`, `quiz_engine`, `results`, `observability` — each with its own `api → service → repository`(`→ domain`) layering), deployed as four cooperating processes (API, worker, stream consumer, beat). See [ADR 0004](docs/adr/0004-layered-architecture-per-module.md) and [ADR 0006](docs/adr/0006-modular-monolith.md) for why.

Frontend: Next.js (App Router), httpOnly-cookie auth, server-authoritative exam state (the client never owns the timer or the score).

## Try it

```bash
docker compose up -d                              # postgres, redis, backend, worker, stream_consumer, beat
cd backend && uv run alembic upgrade head
uv run python -m scripts.seed_demo                 # demo instructor/student + a real question pool
cd ../frontend && npm install && npm run dev        # http://localhost:3000
```
Demo accounts printed by `seed_demo`: `instructor@skilltrace.dev` / `student@skilltrace.dev`, password `Passw0rd!demo`.

Run the tests:
```bash
cd backend && uv run pytest                         # 257 integration tests against a real Postgres + Redis
cd frontend && npm run build && npm run e2e          # 6 real-browser (Playwright) end-to-end journeys
```

A local, docker-composed production-style deployment (built images, an nginx reverse proxy verifying WebSocket passthrough) is in `docker-compose.prod.yml` — see [ADR 0013](docs/adr/0013-websocket-deployment-verification.md). An actual cloud deployment needs your own hosting accounts; see **What's NOT built**.

## Key design decisions

Full architecture decision records in [`docs/adr/`](docs/adr/) — highlights:

| ADR | Decision |
|---|---|
| [0003](docs/adr/0003-bkt-parameter-snapshotting.md) | BKT parameters are snapshotted per-answer, never re-read at grading time |
| [0005](docs/adr/0005-schema-verification-notes.md) | The ORM models + migrations are the source of truth, not the design docs |
| [0006](docs/adr/0006-modular-monolith.md) | Modular monolith, not microservices — and why that's a real tradeoff, not a shortcut |
| [0008](docs/adr/0008-concurrency-testing-results.md) | Concurrency/chaos testing results, stated honestly (including what wasn't tested) |
| [0009](docs/adr/0009-distributed-locking-strategy.md) | Distributed exam-start locking: atomic Redis lock + a DB constraint backstop |
| [0010](docs/adr/0010-websocket-authorization-ordering.md) | WebSocket authorization must resolve before `accept()` |
| [0011](docs/adr/0011-durable-submission-pipeline.md) | The two-write pattern (Postgres commit, then Redis push) + Streams consumer groups |
| [0012](docs/adr/0012-precomputed-exam-results.md) | Precomputed exam results via a materialized view, refreshed once per close |

## What's NOT built (and why)

- **Proctoring, plagiarism/tab-switch detection.** Out of scope by design — this project is about the mastery-tracking and concurrency engineering, not exam-integrity surveillance, which is its own large and separately-hard problem.
- **LLM-based free-text grading.** Text-input answers use normalized exact/near matching, deliberately — see the PRD's own framing: fuzzy/NLP grading is a time sink orthogonal to proving the BKT math and the concurrency guarantees are correct, which is the actual point of this project.
- **Learning BKT's own parameters from data (Baum-Welch/EM).** Parameters are literature-standard defaults, editable per skill by an instructor, not fit from observed data. A known, named simplification — the standard BKT assumption set, not an oversight.
- **A real cloud deployment.** Dockerfiles, a production compose file, an env checklist, and a real (if locally-scoped) WebSocket-through-reverse-proxy verification all exist — see [ADR 0013](docs/adr/0013-websocket-deployment-verification.md) for exactly what was and wasn't possible to verify without a hosting account. Actually provisioning Postgres/Redis/API/worker/frontend on a real platform needs credentials this environment doesn't have.
- **Multi-tenancy.** One shared instructor/student/skill space. Straightforward to add (an `org_id` column and a scoped-query convention) but not built, because nothing in this project's scope needed it.
