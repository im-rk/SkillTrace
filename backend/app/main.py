from fastapi import FastAPI
from app.modules.iam.api import router as iam_router

app = FastAPI(title="SkillTrace Exam Platform")

app.include_router(iam_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
