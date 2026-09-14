"""
Main API v1 router that aggregates all module routers.
"""
from fastapi import APIRouter
from app.modules.iam.api import router as iam_router
from app.modules.question_bank.api import router as question_bank_router
from app.modules.scheduling.api import router as scheduling_router

router = APIRouter()
router.include_router(iam_router)
router.include_router(question_bank_router)
router.include_router(scheduling_router)
