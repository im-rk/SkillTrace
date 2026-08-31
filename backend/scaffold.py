import os
from pathlib import Path

# Mapping of file paths to their descriptions based on the structure doc
files_to_create = {
    "app/main.py": "\"\"\"\nMain FastAPI application entrypoint.\nMounts the WebSocket router and provides Celery app reference.\n\"\"\"",
    "app/core/config.py": "\"\"\"\nApplication configuration using pydantic-settings.\nIncludes REDIS_URL, CELERY_BROKER_URL, and other env vars.\n\"\"\"",
    "app/core/security.py": "\"\"\"\nSecurity utilities.\nPassword hashing (bcrypt/argon2) and JWT encode/decode.\n\"\"\"",
    "app/core/redis_client.py": "\"\"\"\nShared Redis connection.\nUsed by distributed locks, pub/sub for websockets, and streams.\n\"\"\"",
    "app/core/celery_app.py": "\"\"\"\nCelery application instance and configuration.\n\"\"\"",
    "app/core/logging.py": "\"\"\"\nStructured logging configuration.\n\"\"\"",
    "app/core/exceptions.py": "\"\"\"\nCustom exception classes and global error handlers.\n\"\"\"",
    
    # IAM Module
    "app/modules/iam/models.py": "\"\"\"\nDatabase models for IAM.\nIncludes User (roles: student/instructor/admin).\n\"\"\"",
    "app/modules/iam/schemas.py": "\"\"\"\nPydantic schemas for IAM request/response payloads.\n\"\"\"",
    "app/modules/iam/repository.py": "\"\"\"\nData access repository for IAM.\n\"\"\"",
    "app/modules/iam/service.py": "\"\"\"\nBusiness logic service for IAM (AuthService).\n\"\"\"",
    "app/modules/iam/api.py": "\"\"\"\nREST API routes for IAM.\nIncludes /auth/register, /auth/login.\n\"\"\"",
    "app/modules/iam/deps.py": "\"\"\"\nFastAPI dependencies for IAM.\nIncludes get_current_user, require_admin, require_instructor.\n\"\"\"",
    
    # Question Bank Module
    "app/modules/question_bank/models.py": "\"\"\"\nDatabase models for Question Bank.\nIncludes Question (polymorphic JSONB), Tag, QuestionTag.\n\"\"\"",
    "app/modules/question_bank/schemas.py": "\"\"\"\nPydantic schemas for Question Bank.\nIncludes per-type content schemas (MCQContent, TrueFalseContent, TextInputContent).\n\"\"\"",
    "app/modules/question_bank/repository.py": "\"\"\"\nData access repository for Question Bank.\n\"\"\"",
    "app/modules/question_bank/service.py": "\"\"\"\nBusiness logic service for Question Bank.\n\"\"\"",
    "app/modules/question_bank/bulk_import_service.py": "\"\"\"\nService for CSV/JSON parsing, per-row validation, and partial-success reporting.\n\"\"\"",
    "app/modules/question_bank/api.py": "\"\"\"\nREST API routes for Question Bank.\nIncludes POST /question-bank/bulk-import.\n\"\"\"",
    
    # Scheduling Module
    "app/modules/scheduling/models.py": "\"\"\"\nDatabase models for Scheduling.\nIncludes Exam, ExamQuestion.\n\"\"\"",
    "app/modules/scheduling/schemas.py": "\"\"\"\nPydantic schemas for Scheduling.\n\"\"\"",
    "app/modules/scheduling/repository.py": "\"\"\"\nData access repository for Scheduling.\n\"\"\"",
    "app/modules/scheduling/service.py": "\"\"\"\nBusiness logic service for Scheduling (ExamService).\nHandles creating/scheduling exams and assigning questions.\n\"\"\"",
    "app/modules/scheduling/locking.py": "\"\"\"\nRedis distributed lock wrapper for concurrency control during exam start.\n\"\"\"",
    "app/modules/scheduling/api.py": "\"\"\"\nREST API routes for Scheduling.\nIncludes /exams, /exams/{id}/start.\n\"\"\"",
    
    # Enrollment Module
    "app/modules/enrollment/models.py": "\"\"\"\nDatabase models for Enrollment.\nIncludes ExamEnrollment, ExamAccessCode.\n\"\"\"",
    "app/modules/enrollment/schemas.py": "\"\"\"\nPydantic schemas for Enrollment.\n\"\"\"",
    "app/modules/enrollment/repository.py": "\"\"\"\nData access repository for Enrollment.\n\"\"\"",
    "app/modules/enrollment/service.py": "\"\"\"\nBusiness logic service for Enrollment (EnrollmentService).\nHandles manual enroll, generate/redeem access codes.\n\"\"\"",
    "app/modules/enrollment/deps.py": "\"\"\"\nFastAPI dependencies for Enrollment.\nIncludes verify_exam_access (REST) + verify_exam_access_ws (WebSocket).\n\"\"\"",
    "app/modules/enrollment/api.py": "\"\"\"\nREST API routes for Enrollment.\nIncludes /exams/{id}/enroll, /exams/{id}/access-codes.\n\"\"\"",
    
    # Live Session Gateway Module
    "app/modules/live_session_gateway/models.py": "\"\"\"\nDatabase models for Live Session Gateway.\nIncludes ExamSession (in_progress/paused_disconnected/submitted/...).\n\"\"\"",
    "app/modules/live_session_gateway/schemas.py": "\"\"\"\nPydantic schemas for Live Session Gateway.\n\"\"\"",
    "app/modules/live_session_gateway/repository.py": "\"\"\"\nData access repository for Live Session Gateway.\n\"\"\"",
    "app/modules/live_session_gateway/service.py": "\"\"\"\nBusiness logic service for Live Session Gateway (SessionService).\nHandles heartbeat handling, pause/resume logic.\n\"\"\"",
    "app/modules/live_session_gateway/websocket_manager.py": "\"\"\"\nWebSocket connection registry and Redis Pub/Sub subscriber/broadcaster.\n\"\"\"",
    "app/modules/live_session_gateway/ws_routes.py": "\"\"\"\nWebSocket endpoints for live sessions.\nUses handshake auth via enrollment.deps.\n\"\"\"",
    
    # Evaluation Pipeline Module
    "app/modules/evaluation_pipeline/schemas.py": "\"\"\"\nPydantic schemas for Evaluation Pipeline.\nIncludes SubmissionPayload.\n\"\"\"",
    "app/modules/evaluation_pipeline/queue_producer.py": "\"\"\"\nQueue producer for evaluation pipeline.\nWrites submission_queue_log row and pushes to Redis Stream.\n\"\"\"",
    "app/modules/evaluation_pipeline/tasks.py": "\"\"\"\nCelery tasks for evaluation pipeline.\nConsumes stream, calls quiz_engine's BKT engine, and persists data.\n\"\"\"",
    "app/modules/evaluation_pipeline/api.py": "\"\"\"\nREST API routes for Evaluation Pipeline.\nIncludes POST /exam-sessions/{id}/submit-answer (fast path: log + enqueue only).\n\"\"\"",
    
    # Quiz Engine Module (BKT Domain)
    "app/modules/quiz_engine/domain/bkt/params.py": "\"\"\"\nBKT domain parameters.\n\"\"\"",
    "app/modules/quiz_engine/domain/bkt/engine.py": "\"\"\"\nBKT domain logic engine.\nCalculates forward algorithm updates.\n\"\"\"",
    "app/modules/quiz_engine/domain/bkt/policy.py": "\"\"\"\nBKT domain logic policy.\n\"\"\"",
    "app/modules/quiz_engine/domain/validation/answer_matching.py": "\"\"\"\nDomain validation for answer matching.\n\"\"\"",
    "app/modules/quiz_engine/models.py": "\"\"\"\nDatabase models for Quiz Engine.\nIncludes StudentSkillState.\n\"\"\"",
    "app/modules/quiz_engine/repository.py": "\"\"\"\nData access repository for Quiz Engine.\n\"\"\"",
    "app/modules/quiz_engine/service.py": "\"\"\"\nBusiness logic service for Quiz Engine.\n\"\"\"",
    "app/modules/quiz_engine/api.py": "\"\"\"\nREST API routes for Quiz Engine.\nServes the v1 free-practice adaptive quiz flow.\n\"\"\"",
    
    # Results Module
    "app/modules/results/schemas.py": "\"\"\"\nPydantic schemas for Results.\n\"\"\"",
    "app/modules/results/repository.py": "\"\"\"\nData access repository for Results.\nIncludes queries against mv_exam_results.\n\"\"\"",
    "app/modules/results/refresh_service.py": "\"\"\"\nService to trigger materialized view refresh (called by a Celery task on exam close).\n\"\"\"",
    "app/modules/results/api.py": "\"\"\"\nREST API routes for Results.\nIncludes /exams/{id}/results (post-close dashboard).\n\"\"\"",
    
    "app/api/v1/router.py": "\"\"\"\nMain API v1 router that aggregates all module routers.\n\"\"\"",
    
    # Worker
    "worker/celery_worker.py": "\"\"\"\nCelery worker entrypoint.\nRun with `celery -A worker.celery_worker worker`.\n\"\"\"",
    "worker/beat_schedule.py": "\"\"\"\nCelery beat periodic tasks schedule (e.g., auto-submit exams past end_time).\n\"\"\"",
    
    # Tests
    "tests/integration/scheduling/test_concurrent_start_lock.py": "\"\"\"\nTest simulating N concurrent start-exam requests.\n\"\"\"",
    "tests/integration/enrollment/test_access_control_rest.py": "\"\"\"\nTest verify_exam_access 403 cases for REST endpoints.\n\"\"\"",
    "tests/integration/enrollment/test_access_control_ws.py": "\"\"\"\nTest WebSocket handshake rejection for unauthorized users.\n\"\"\"",
    "tests/integration/evaluation_pipeline/test_queue_durability.py": "\"\"\"\nChaos test for kill-worker-mid-processing to ensure zero dropped submissions.\n\"\"\"",
    "tests/conftest.py": "\"\"\"\nPytest configuration, fixtures including Redis test fixture and Celery eager-mode fixture.\n\"\"\"",
    
    # Infra & Config files
    "infra/docker/backend.Dockerfile": "# Dockerfile for the backend API process\n",
    "infra/docker/worker.Dockerfile": "# Dockerfile for the Celery worker process\n",
    ".env": "# Environment variables\nREDIS_URL=redis://localhost:6379/0\nCELERY_BROKER_URL=redis://localhost:6379/1\nCELERY_RESULT_BACKEND=redis://localhost:6379/2\nEXAM_START_LOCK_TTL_MS=5000\n",
    "Dockerfile": "# Root Dockerfile (if needed, otherwise rely on infra/docker/backend.Dockerfile)\n",
    "../docker-compose.yml": "services:\n  redis:\n    image: redis:7-alpine\n    ports: [\"6379:6379\"]\n  postgres:\n    image: postgres:15-alpine\n    environment:\n      POSTGRES_USER: user\n      POSTGRES_PASSWORD: password\n      POSTGRES_DB: skilltrace\n    ports: [\"5432:5432\"]\n"
}

def create_files():
    for file_path, content in files_to_create.items():
        # Handle the root directory for docker-compose
        full_path = Path(file_path).resolve()
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if not full_path.exists():
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
                print(f"Created {file_path}")

if __name__ == "__main__":
    create_files()
    print("All files created with their descriptions.")
