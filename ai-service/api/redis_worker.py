import asyncio
import json
import redis.asyncio as redis
from api.routes.kb import process_document

async def listen_redis_queue():
    print("Redis queue listener started...")
    
    # 建立长连接，redis-py 内置连接池，断开会自动重连。
    # 显式设置 socket_timeout=10 (略大于 blpop 的 timeout 5)，
    # 避免 Python 客户端的默认 socket_timeout 过短导致 blpop 时抛出 TimeoutError，从而陷入 5s 重连死循环
    r = redis.Redis(
        host='localhost', 
        port=6379, 
        db=0, 
        password='aegis123', 
        health_check_interval=30, 
        protocol=2,
        socket_timeout=10
    )
    
    try:
        while True:
            try:
                # timeout 改为 5，避免死等导致被服务端或操作系统悄悄掐断连接
                result = await r.blpop("rag_parse_queue", timeout=5)
                if result:
                    queue_name, message = result
                    try:
                        data = json.loads(message.decode('utf-8'))
                        doc_id = data.get("documentId")
                        file_path = data.get("filePath")
                        if doc_id and file_path:
                            print(f"Received task from Redis: doc_id={doc_id}, file_path={file_path}")
                            # Execute the parsing task (this runs asynchronously inside the event loop)
                            asyncio.create_task(process_document_async_wrapper(doc_id, file_path))
                    except Exception as e:
                        print(f"Error processing Redis message: {e}")
            except redis.exceptions.TimeoutError:
                # 极端情况下如果 socket_timeout 仍被触发，忽略即可，下一轮会继续 blpop
                pass
            except Exception as e:
                print(f"Redis listener error: {e}, retrying in 5s...")
                await asyncio.sleep(5)
    finally:
        await r.aclose()

async def process_document_async_wrapper(document_id: int, file_path: str):
    # process_document is a sync function that calls asyncio.run inside, 
    # we need to refactor process_document to be an async function to avoid blocking the event loop.
    from api.routes.kb import _process
    await _process(document_id, file_path)