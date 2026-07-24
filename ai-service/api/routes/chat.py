from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import urllib.request
import json

router = APIRouter()

class QueryRequest(BaseModel):
    question: str

@router.post("/internal/rag/query")
def rag_query(request: QueryRequest):
    ollama_url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:7b",
        "prompt": request.question,
        "stream": False
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        # 创建请求，显式移除代理
        req = urllib.request.Request(ollama_url, data=data, headers={'Content-Type': 'application/json'})
        
        # 使用不带代理的 opener
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        
        with opener.open(req, timeout=60.0) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {"answer": result.get("response", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama request failed: {str(e)}")
