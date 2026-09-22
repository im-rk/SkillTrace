"""
Main API v1 router that aggregates all module routers.
"""
from fastapi import APIRouter
from app.modules.iam.api import router as iam_router
from app.modules.question_bank.api import router as question_bank_router
from app.modules.scheduling.api import router as scheduling_router
from app.modules.enrollment.api import router as enrollment_router
from app.modules.evaluation_pipeline.api import router as evaluation_pipeline_router
from app.modules.results.api import router as results_router
from app.modules.live_session_gateway.api import router as live_session_gateway_router
from app.modules.quiz_engine.api import router as quiz_engine_router
from app.modules.observability.api import router as observability_router

router = APIRouter()
router.include_router(iam_router)
router.include_router(question_bank_router)
router.include_router(scheduling_router)
router.include_router(enrollment_router)
router.include_router(evaluation_pipeline_router)
router.include_router(results_router)
router.include_router(live_session_gateway_router)
router.include_router(quiz_engine_router)
router.include_router(observability_router)
