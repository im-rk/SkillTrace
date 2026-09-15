import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.router import router as api_router
from app.core.redis_client import close_redis, get_redis
from app.modules.live_session_gateway.websocket_manager import connection_manager, run_subscriber_forever
from app.modules.live_session_gateway.ws_routes import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    subscriber_task = asyncio.create_task(run_subscriber_forever(get_redis(), connection_manager))
    yield
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass
    await close_redis()


app = FastAPI(title="SkillTrace Exam Platform", lifespan=lifespan)

app.include_router(api_router)
app.include_router(ws_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
