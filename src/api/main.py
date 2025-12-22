from fastapi import FastAPI
import uvicorn
from src.api.endpoints import router

app = FastAPI(
    title="EMU RAG API",
    description="API for the Eastern Mediterranean University RAG system",
    version="0.1.0",
    root_path="/api/v1",
)

@app.get("/")
async def root():
    return {"message": "Eastern Mediterranean University RAG API"}

@app.get("/health")
async def health():
    return {"message": "OK"}

app.include_router(router)

"""uvicorn.run(app, host="0.0.0.0", port=8000)"""
