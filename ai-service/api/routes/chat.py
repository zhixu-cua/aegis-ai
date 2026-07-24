import json
import time
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class QueryRequest(BaseModel):
    question: str

@router.post("/internal/rag/query")
def rag_query(request: QueryRequest):
    ollama_url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "qwen:0.5b",
        "prompt": request.question,
        "stream": False,
        "keep_alive": "10m"
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ollama_url,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    # 显式绕过系统代理，避免本地服务请求被代理软件干扰。
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)

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
