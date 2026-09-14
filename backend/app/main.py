from fastapi import FastAPI
from app.api.v1.router import router as api_router

app = FastAPI(title="SkillTrace Exam Platform")

app.include_router(api_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
