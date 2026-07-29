import json
import urllib.request
import urllib.error
import asyncpg
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()

class IngestRequest(BaseModel):
    documentId: int
    filePath: str

def process_document(document_id: int, file_path: str):
    async def _process():
        conn = None
        try:
            conn = await asyncpg.connect(
                host="localhost",
                port=5433,
                database="aegis_assistant",
                user="aegis",
                password="aegis123"
            )
            
            # Read file with encoding fallback and basic binary check
            text = ""
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, "r", encoding="gbk") as f:
                        text = f.read()
                except UnicodeDecodeError:
                    # Fallback to ignore errors if it's a weird text file, but reject if it looks like binary
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                        if '\x00' in text:
                            raise Exception("文件格式不支持: 目前仅支持 txt/md 纯文本文件，请勿上传图片或 Word/PDF 等二进制文件。")
                            
            if not text.strip():
                raise Exception("文件内容为空")
                
            # Semantic chunking (语义分块)
            import re
            sentences = re.split(r'(?<=[。！？!?\n])', text)
            chunks = []
            current_chunk = ""
            # 可调参数: max_len 语义分块的最大字符长度，可以根据业务文档的长短调节（如 500-1000）
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
                # Call Ollama for embedding
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
                    with opener.open(req, timeout=120.0) as response:
                        result = json.loads(response.read().decode("utf-8"))
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

    asyncio.run(_process())

@router.post("/internal/rag/ingest")
def rag_ingest(request: IngestRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_document, request.documentId, request.filePath)
    return {"message": "Ingestion started"}
