import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.routes import health, chat, kb
from api.redis_worker import listen_redis_queue

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize connections to PostgreSQL, Redis, MinIO, Ollama here
    # Start Redis listener task
    task = asyncio.create_task(listen_redis_queue())
    yield
    # Close connections here
    task.cancel()

app = FastAPI(title="售后助手 AI 服务", lifespan=lifespan)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(kb.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
