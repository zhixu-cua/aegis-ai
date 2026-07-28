import json
import time
import urllib.error
import urllib.request
import asyncpg
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class QueryRequest(BaseModel):
    question: str

@router.post("/internal/rag/query")
def rag_query(request: QueryRequest):
    # 显式绕过系统代理，避免本地服务请求被代理软件干扰。
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)

    # 1. Generate embedding for the question using nomic-embed-text
    ollama_embed_url = "http://127.0.0.1:11434/api/embeddings"
    embed_payload = {
        "model": "nomic-embed-text",
        "prompt": request.question
    }
    embed_req = urllib.request.Request(
        ollama_embed_url,
        data=json.dumps(embed_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with opener.open(embed_req, timeout=120.0) as response:
            result = json.loads(response.read().decode("utf-8"))
            question_embedding = result.get("embedding")
            if not question_embedding:
                raise Exception("Failed to generate embedding for question")
    except urllib.error.HTTPError as he:
        if he.code == 404:
            raise HTTPException(status_code=500, detail="Ollama 报错 404: 缺少向量模型。请在终端执行 'ollama pull nomic-embed-text'")
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(he)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

    # 2. Query kb_chunk for top 3 closest chunks using pgvector
    chunks_text = []
    try:
        async def _query_db():
            conn = await asyncpg.connect(
                host="localhost",
                port=5433,
                database="aegis_assistant",
                user="aegis",
                password="aegis123"
            )
            try:
                rows = await conn.fetch(
                    """
                    SELECT chunk_text 
                    FROM kb_chunk 
                    ORDER BY embedding <=> $1::vector 
                    LIMIT 3
                    """,
                    str(question_embedding)
                )
                return [row['chunk_text'] for row in rows]
            finally:
                await conn.close()

        chunks_text = asyncio.run(_query_db())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

    # 3. Construct RAG prompt
    context = "\n\n".join(chunks_text)
    prompt = f"Context: {context}\nQuestion: {request.question}"

    # 4. Send the new prompt to qwen:1.8b
    ollama_url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "qwen:1.8b",
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m"
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ollama_url,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    last_error = "未知错误"
    for attempt in range(3):
        try:
            with opener.open(req, timeout=120.0) as response:
                result = json.loads(response.read().decode("utf-8"))
                answer = result.get("response", "").strip()
                if not answer:
                    raise HTTPException(status_code=502, detail="Ollama 返回空响应")
                return {"answer": answer}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            last_error = f"HTTP {e.code}: {error_body or e.reason}"
        except Exception as e:
            last_error = str(e)

        if attempt < 2:
            time.sleep(1)

    raise HTTPException(status_code=500, detail=f"Ollama request failed after retries: {last_error}")
