from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.routes import health

@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: Initialize connections to PostgreSQL, Redis, MinIO, Ollama here
    yield
    # TODO: Close connections here

app = FastAPI(title="售后助手 AI 服务", lifespan=lifespan)

app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
