import asyncio
import json
import redis.asyncio as redis
from api.routes.kb import process_document

async def listen_redis_queue():
    # 增加 health_check_interval 保持底层 TCP 连接活跃
    r = redis.Redis(host='localhost', port=6379, db=0, password='aegis123', protocol=2, health_check_interval=30)
    print("Redis queue listener started...")
    while True:
        try:
            # timeout 改为 30，避免死等 0 导致被服务端或操作系统悄悄掐断连接
            result = await r.blpop("rag_parse_queue", timeout=30)
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
        except Exception as e:
            if "Timeout" in str(e.__class__.__name__) or "Timeout" in str(e):
                # 正常的网络超时或连接检测超时，直接进行下一次循环即可
                continue
            print(f"Redis listener encountered an error: {e}, retrying in 5 seconds...")
            await asyncio.sleep(5)

async def process_document_async_wrapper(document_id: int, file_path: str):
    # process_document is a sync function that calls asyncio.run inside, 
    # we need to refactor process_document to be an async function to avoid blocking the event loop.
    from api.routes.kb import _process
    await _process(document_id, file_path)