from fastapi import FastAPI
import uvicorn
from src.api.routers.rag import router as rag_router
from src.api.routers.auth import router as auth_router
from src.api.routers.user import router as user_router
from src.api.routers.sessions import router as session_router
from src.api.dependencies.clients import get_redis_client, get_redis
from fastapi_limiter import FastAPILimiter
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_instance = get_redis()
    await FastAPILimiter.init(redis_instance)
    yield

app = FastAPI(
    title="EMU RAG API",
    description="API for the Eastern Mediterranean University RAG system",
    version="0.1.0",
    #root_path="/api/v1",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"message": "Eastern Mediterranean University RAG API"}

@app.get("/health")
async def health():
    return {"message": "OK"}

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(session_router)
app.include_router(rag_router)


"""uvicorn.run(app, host="0.0.0.0", port=8000)"""
