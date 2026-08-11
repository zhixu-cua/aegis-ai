import asyncio
import os
import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.routes import health, chat, kb
from api.redis_worker import listen_redis_queue
from api.command_listener import listen_commands
from api.services.ingestion.worker import create_worker, DocumentWorker

# 全局变量
pg_pool: asyncpg.Pool = None
redis_client: redis.Redis = None
worker: DocumentWorker = None
worker_task: asyncio.Task = None
redis_queue_task: asyncio.Task = None
command_listener_task: asyncio.Task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pg_pool, redis_client, worker, worker_task, redis_queue_task, command_listener_task
    
    # 1. 初始化 PostgreSQL 连接池
    pg_pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5433"),
        database=os.getenv("DB_NAME", "aegis_assistant"),
        user=os.getenv("DB_USER", "aegis"),
        password=os.getenv("DB_PASSWORD", "aegis123"),
        min_size=5,
        max_size=20
    )
    
    # 2. 初始化 Redis 连接
    redis_url = os.getenv("REDIS_URL", "redis://:aegis123@localhost:6379/0")
    redis_client = redis.Redis(host='localhost', port=6379, db=0, password='aegis123', protocol=2)
    
    # 3. 启动 Worker
    worker = await create_worker(
        pg_pool=pg_pool,
        redis_url=redis_url,
        backend_url=os.getenv("BACKEND_URL", "http://localhost:8082")
    )
    worker_task = asyncio.create_task(worker.start())

    # Start Redis listener task
    redis_queue_task = asyncio.create_task(listen_redis_queue())
    command_listener_task = asyncio.create_task(listen_commands())
    
    yield
    
    # Close connections here
    if command_listener_task:
        command_listener_task.cancel()
    if redis_queue_task:
        redis_queue_task.cancel()
    if worker_task:
        worker_task.cancel()
    if pg_pool:
        await pg_pool.close()
    if redis_client:
        await redis_client.close()

app = FastAPI(title="售后助手 AI 服务", lifespan=lifespan)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(kb.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
