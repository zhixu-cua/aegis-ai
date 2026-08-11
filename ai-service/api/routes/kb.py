import json
import urllib.request
import urllib.error
import asyncpg
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from api.services.ingestion.parser import parse_document

router = APIRouter()

class IngestRequest(BaseModel):
    documentId: int
    filePath: str

async def _process(document_id: int, file_path: str):
    conn = None
    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5433,
            database="aegis_assistant",
            user="aegis",
            password="aegis123"
        )
        
        # 多模态文件解析
        text = parse_document(file_path)
        
        if not text or not text.strip():
            raise Exception("文件内容为空或无法提取文本")
            
        # Semantic chunking (语义分块)
        import re
        # 使用更合理的切分逻辑，优先换行，其次句号
        sentences = re.split(r'(?<=[。！？!?\n])', text)
        chunks = []
        current_chunk = ""
        max_len = 500
        for sentence in sentences:
            if not sentence.strip():
                continue
            if len(current_chunk) + len(sentence) <= max_len:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        ollama_url = "http://127.0.0.1:11434/api/embeddings"
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        
        for idx, chunk in enumerate(chunks):
            payload = {
                "model": "nomic-embed-text",
                "prompt": chunk
            }
            req = urllib.request.Request(
                ollama_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            
            try:
                # 异步运行 urllib 防止阻塞事件循环
                def _fetch_embedding():
                    with opener.open(req, timeout=120.0) as response:
                        return json.loads(response.read().decode("utf-8"))
                result = await asyncio.to_thread(_fetch_embedding)
                embedding = result.get("embedding")
                
                if not embedding:
                    raise Exception(f"Failed to generate embedding for chunk {idx}")
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    raise Exception("Ollama 报错 404: 缺少向量模型。请在终端执行 'ollama pull nomic-embed-text' 进行下载。")
                raise
                    
            # Insert into kb_chunk
            await conn.execute(
                """
                INSERT INTO kb_chunk (document_id, chunk_index, chunk_text, embedding)
                VALUES ($1, $2, $3, $4::vector)
                """,
                document_id, idx, chunk, str(embedding)
            )
            
        # Update kb_document status to SUCCESS
        await conn.execute(
            """
            UPDATE kb_document
            SET status = 'SUCCESS', parse_message = 'Document processed successfully', updated_at = now()
            WHERE id = $1
            """,
            document_id
        )
        print(f"Document {document_id} processed successfully.")
        
    except Exception as e:
        if conn:
            try:
                await conn.execute(
                    """
                    UPDATE kb_document
                    SET status = 'FAILED', parse_message = $1, updated_at = now()
                    WHERE id = $2
                    """,
                    str(e), document_id
                )
            except Exception as inner_e:
                print(f"Failed to update document status to FAILED: {inner_e}")
        print(f"Error processing document {document_id}: {e}")
        
    finally:
        if conn:
            await conn.close()

def process_document(document_id: int, file_path: str):
    asyncio.run(_process(document_id, file_path))

@router.post("/internal/rag/ingest")
def rag_ingest(request: IngestRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_document, request.documentId, request.filePath)
    return {"message": "Ingestion started"}
